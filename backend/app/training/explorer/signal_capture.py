"""
Browser signal capture: DOM delta, network trace, console errors.
Wraps Playwright page with event listeners that accumulate signals per page visit.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from playwright.async_api import Page, Request, Response


@dataclass
class NetworkRecord:
    method: str
    url: str
    request_body: Any = None
    response_status: int | None = None
    response_body: Any = None


@dataclass
class DomDelta:
    changed: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)


class SignalCapture:
    """Attached to a Playwright Page. Accumulates signals until flush() is called."""

    def __init__(self, page: Page) -> None:
        self._page = page
        self._network: list[NetworkRecord] = []
        self._console_errors: list[str] = []
        self._dom_before: str = ""
        page.on("request", self._on_request)
        page.on("response", self._on_response)
        page.on("console", self._on_console)

    def _on_request(self, request: Request) -> None:
        pass  # captured at response time to include status

    def _on_response(self, response: Response) -> None:
        self._network.append(
            NetworkRecord(
                method=response.request.method,
                url=response.url,
                response_status=response.status,
            )
        )

    def _on_console(self, msg: Any) -> None:
        if msg.type == "error":
            self._console_errors.append(msg.text)

    async def snapshot_dom(self) -> None:
        """Call before an action to capture before-state."""
        self._dom_before = await self._page.evaluate(
            "() => document.body.innerHTML"
        )

    async def compute_delta(self) -> DomDelta:
        """Call after an action to compute what changed."""
        dom_after = await self._page.evaluate("() => document.body.innerHTML")
        # Simplified diff: detect presence changes via element fingerprints
        before_lines = set(self._dom_before.splitlines())
        after_lines = set(dom_after.splitlines())
        added = [l.strip() for l in (after_lines - before_lines) if l.strip() and len(l.strip()) < 200]
        removed = [l.strip() for l in (before_lines - after_lines) if l.strip() and len(l.strip()) < 200]
        return DomDelta(added=added[:20], removed=removed[:20])

    def flush_network(self) -> list[NetworkRecord]:
        records = list(self._network)
        self._network.clear()
        return records

    def flush_console(self) -> list[str]:
        errors = list(self._console_errors)
        self._console_errors.clear()
        return errors

    @staticmethod
    def fingerprint(url: str, dom_summary: str) -> str:
        return hashlib.md5(f"{url}:{dom_summary[:500]}".encode()).hexdigest()
