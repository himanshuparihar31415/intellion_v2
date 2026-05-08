"""
ExplorationAgent: long-running asyncio task that crawls a target app
and writes structural + interaction knowledge nodes to the graph.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import asyncpg
from playwright.async_api import async_playwright, BrowserContext, Page

from ...db.repositories import NodeRepository, SessionRepository
from ...models.enums import SourceType
from ...services.write_pipeline import NodeWritePipeline, RawSignal
from .action_executor import ActionSuggestion, execute_action, suggest_next_action
from .frontier import FrontierItem, FrontierScheduler
from .signal_capture import SignalCapture

_MAX_STEPS_PER_SESSION = 200


@dataclass
class ExplorationStatus:
    session_id: uuid.UUID
    steps_taken: int
    nodes_written: int
    coverage_score: float
    running: bool


class ExplorationAgent:
    """
    Crawls target_url, runs action suggestion loop, writes signals
    through NodeWritePipeline. One agent per training session.
    """

    def __init__(
        self,
        conn: asyncpg.Connection,
        intellion_id: uuid.UUID,
        session_id: uuid.UUID,
        target_url: str,
    ) -> None:
        self._conn = conn
        self._intellion_id = intellion_id
        self._session_id = session_id
        self._target_url = target_url
        self._origin = urlparse(target_url).scheme + "://" + urlparse(target_url).netloc
        self._pipeline = NodeWritePipeline(
            conn, intellion_id, session_id, SourceType.EXPLORATION
        )
        self._frontier = FrontierScheduler(conn, intellion_id, session_id)
        self._nodes_written = 0
        self._steps_taken = 0
        self._running = False
        self._visited_fingerprints: set[str] = set()
        self._visited_urls: set[str] = set()

    async def run(self) -> ExplorationStatus:
        """Main exploration loop. Call in background task."""
        self._running = True
        await self._frontier.load_pending()
        if self._frontier.size() == 0:
            self._frontier.seed_from_url(self._target_url)

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context: BrowserContext = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                ignore_https_errors=True,
            )
            page: Page = await context.new_page()
            capture = SignalCapture(page)

            try:
                await self._exploration_loop(page, capture)
            finally:
                await context.close()
                await browser.close()
                self._running = False

        coverage = await self._frontier.structural_coverage()
        session_repo = SessionRepository(self._conn)
        await session_repo.complete(self._session_id, coverage_score=coverage)

        return ExplorationStatus(
            session_id=self._session_id,
            steps_taken=self._steps_taken,
            nodes_written=self._nodes_written,
            coverage_score=coverage,
            running=False,
        )

    async def _exploration_loop(self, page: Page, capture: SignalCapture) -> None:
        while self._running and self._steps_taken < _MAX_STEPS_PER_SESSION:
            item = self._frontier.pop()
            if item is None:
                break

            await self._frontier.mark_attempted(item.item_id)

            # Navigate to target URL if specified
            target_url = item.target_url or self._target_url
            if target_url and page.url != target_url:
                try:
                    await page.goto(target_url, wait_until="networkidle", timeout=15000)
                except Exception:
                    await self._frontier.mark_done(item.item_id)
                    continue

            # Check visited state
            fp = SignalCapture.fingerprint(page.url, await page.title())
            if fp in self._visited_fingerprints:
                await self._frontier.mark_done(item.item_id)
                continue
            self._visited_fingerprints.add(fp)
            self._visited_urls.add(page.url)

            # Get graph context for this page
            node_repo = NodeRepository(self._conn)
            existing = await node_repo.list_active(self._intellion_id, page=0, page_size=10)
            graph_context = [n.semantic_definition for n in existing[:10]]

            # Ask Claude for next action
            action = await suggest_next_action(page, graph_context, self._visited_urls)
            if action is None:
                await self._frontier.mark_done(item.item_id)
                continue

            # Capture before-state, execute, capture after-state
            await capture.snapshot_dom()
            network_before_count = len(capture.flush_network())

            success = await execute_action(page, action)
            self._steps_taken += 1

            if not success:
                await self._frontier.mark_done(item.item_id)
                continue

            await asyncio.sleep(0.5)  # brief settle
            dom_delta = await capture.compute_delta()
            network_records = capture.flush_network()

            # Build raw signal
            path = urlparse(page.url).path or "/"
            signal = RawSignal(
                page_url=page.url,
                page_path=path,
                action_type=action.action_type,
                action_selector=action.selector,
                dom_delta={
                    "changed": [],
                    "added": dom_delta.added,
                    "removed": dom_delta.removed,
                },
                network_trace=[
                    {
                        "method": r.method,
                        "url": r.url,
                        "response_status": r.response_status,
                    }
                    for r in network_records
                    if self._origin in r.url or "/api/" in r.url
                ],
                existing_graph_context="\n".join(graph_context),
            )

            nodes = await self._pipeline.process(signal)
            self._nodes_written += len(nodes)

            # Push newly discovered URLs as frontier items
            await self._enqueue_links(page)
            await self._frontier.mark_done(item.item_id)

    async def _enqueue_links(self, page: Page) -> None:
        """Find unvisited links on the current page and add to frontier."""
        hrefs: list[str] = await page.evaluate(
            """
            () => Array.from(document.querySelectorAll('a[href]'))
                .map(a => a.href)
                .filter(h => h.startsWith(window.location.origin))
                .slice(0, 20)
            """
        )
        for href in hrefs:
            if href not in self._visited_urls:
                path = urlparse(href).path
                item = FrontierItem(
                    target_description=f"Explore page: {path}",
                    target_url=href,
                    created_by_source="exploration",
                    gap_weight=40.0,
                )
                self._frontier.push(item)
                await self._frontier.persist(item)

    def stop(self) -> None:
        self._running = False

    @property
    def status(self) -> dict:
        return {
            "running": self._running,
            "steps_taken": self._steps_taken,
            "nodes_written": self._nodes_written,
        }
