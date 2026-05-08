"""
FrontierScheduler: priority queue of URLs/states to explore next.
Score = (gap_weight × 0.4) + (confidence_deficit × 0.3) + (doc_intent × 0.2) + (recency_penalty × 0.1)
Two phases: breadth (0-60% structural coverage), then depth.
"""
from __future__ import annotations

import heapq
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import asyncpg


@dataclass
class FrontierItem:
    target_description: str
    target_url: str | None = None
    target_node_id: uuid.UUID | None = None
    created_by_source: str = "exploration"  # exploration | document | manual
    gap_weight: float = 50.0  # 0-100: auth gaps=100, payment=90, cosmetics=20
    confidence_deficit: float = 50.0  # 100 - current_confidence
    doc_intent: bool = False
    last_attempted_at: datetime | None = None
    item_id: uuid.UUID = field(default_factory=uuid.uuid4)

    def priority_score(self) -> float:
        recency_penalty = 0.0
        if self.last_attempted_at:
            hours_since = (datetime.utcnow() - self.last_attempted_at).total_seconds() / 3600
            recency_penalty = min(100.0, hours_since * 4)  # 25 hours to recover full score
        return (
            self.gap_weight * 0.4
            + self.confidence_deficit * 0.3
            + (20.0 if self.doc_intent else 0.0) * 0.2
            + recency_penalty * 0.1
        )

    def __lt__(self, other: FrontierItem) -> bool:
        # Higher score = higher priority (max-heap via negation)
        return self.priority_score() > other.priority_score()


class FrontierScheduler:
    """
    In-memory priority queue backed by persistent DB state.
    Shifts from breadth to depth phase at 60% structural coverage.
    """

    BREADTH_THRESHOLD = 60.0  # % structural coverage to switch phases

    def __init__(
        self,
        conn: asyncpg.Connection,
        intellion_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> None:
        self._conn = conn
        self._intellion_id = intellion_id
        self._session_id = session_id
        self._heap: list[FrontierItem] = []
        self._visited: set[str] = set()  # URL + DOM fingerprint hashes

    # ── Coverage metrics ──────────────────────────────────────────────────────

    async def structural_coverage(self) -> float:
        """Rough estimate: % of structural nodes that have at least one interaction node."""
        row = await self._conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE layer = 1) AS structural_total,
                COUNT(DISTINCT e.source_node_id) FILTER (
                    WHERE n2.layer = 1
                ) AS structural_covered
            FROM nodes n1
            LEFT JOIN edges e ON e.target_node_id = n1.id
            LEFT JOIN nodes n2 ON n2.id = e.source_node_id
            WHERE n1.intellion_id = $1 AND n1.status = 'active'
            """,
            self._intellion_id,
        )
        if not row or not row["structural_total"]:
            return 0.0
        return (row["structural_covered"] or 0) / row["structural_total"] * 100

    def in_depth_phase(self, coverage: float) -> bool:
        return coverage >= self.BREADTH_THRESHOLD

    # ── Queue management ──────────────────────────────────────────────────────

    def push(self, item: FrontierItem) -> None:
        heapq.heappush(self._heap, item)

    def pop(self) -> FrontierItem | None:
        while self._heap:
            item = heapq.heappop(self._heap)
            if item.item_id not in self._visited:
                return item
        return None

    def mark_visited(self, item_id: uuid.UUID) -> None:
        self._visited.add(str(item_id))

    def size(self) -> int:
        return len(self._heap)

    # ── DB persistence ─────────────────────────────────────────────────────────

    async def persist(self, item: FrontierItem) -> None:
        await self._conn.execute(
            """
            INSERT INTO frontier_items (
                id, intellion_id, target_description, target_node_id,
                created_by_source, gap_weight, status, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, 'pending', now())
            ON CONFLICT DO NOTHING
            """,
            item.item_id,
            self._intellion_id,
            item.target_description,
            item.target_node_id,
            item.created_by_source,
            item.gap_weight,
        )

    async def load_pending(self) -> None:
        """Load pending frontier items from DB into the heap (for session resume)."""
        rows = await self._conn.fetch(
            """
            SELECT id, target_description, target_node_id, created_by_source,
                   gap_weight, last_attempted_at
            FROM frontier_items
            WHERE intellion_id = $1 AND status = 'pending'
            ORDER BY gap_weight DESC
            LIMIT 100
            """,
            self._intellion_id,
        )
        for row in rows:
            item = FrontierItem(
                item_id=row["id"],
                target_description=row["target_description"],
                target_node_id=row["target_node_id"],
                created_by_source=row["created_by_source"],
                gap_weight=float(row["gap_weight"]),
                last_attempted_at=row["last_attempted_at"],
            )
            heapq.heappush(self._heap, item)

    async def mark_done(self, item_id: uuid.UUID) -> None:
        await self._conn.execute(
            "UPDATE frontier_items SET status = 'done' WHERE id = $1", item_id
        )

    async def mark_attempted(self, item_id: uuid.UUID) -> None:
        await self._conn.execute(
            "UPDATE frontier_items SET last_attempted_at = now(), status = 'in_progress' WHERE id = $1",
            item_id,
        )

    # ── Default seed items for a new Intellion ────────────────────────────────

    def seed_from_url(self, base_url: str) -> None:
        self.push(
            FrontierItem(
                target_description=f"Explore root: {base_url}",
                target_url=base_url,
                created_by_source="manual",
                gap_weight=100.0,
            )
        )
