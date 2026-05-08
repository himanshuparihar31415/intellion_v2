from __future__ import annotations
import uuid
from datetime import datetime
import asyncpg
from ...models.graph import Conflict
from ...models.enums import ConflictResolution


class ConflictRepository:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    async def insert(self, conflict: Conflict) -> Conflict:
        await self._conn.execute(
            """
            INSERT INTO conflicts (
                id, intellion_id, node_id, source_a_id, source_b_id,
                source_a_claim, source_b_claim, weight_gap, severity,
                auto_resolvable, resolution_type, resolved_by, resolved_at, created_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
            """,
            conflict.id,
            conflict.intellion_id,
            conflict.node_id,
            conflict.source_a_id,
            conflict.source_b_id,
            conflict.source_a_claim,
            conflict.source_b_claim,
            conflict.weight_gap,
            conflict.severity.value,
            conflict.auto_resolvable,
            conflict.resolution_type.value if conflict.resolution_type else None,
            conflict.resolved_by,
            conflict.resolved_at,
            conflict.created_at,
        )
        return conflict

    async def list_unresolved(self, intellion_id: uuid.UUID) -> list[Conflict]:
        rows = await self._conn.fetch(
            """
            SELECT c.*
            FROM conflicts c
            WHERE c.intellion_id = $1
              AND c.resolution_type IS NULL
            ORDER BY
                CASE c.severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                                WHEN 'medium' THEN 2 ELSE 3 END,
                c.auto_resolvable DESC,
                c.created_at DESC
            """,
            intellion_id,
        )
        return [Conflict(**dict(r)) for r in rows]

    async def resolve(
        self,
        conflict_id: uuid.UUID,
        resolution: ConflictResolution,
        resolved_by: uuid.UUID | None = None,
    ) -> None:
        await self._conn.execute(
            """
            UPDATE conflicts
            SET resolution_type = $2, resolved_by = $3, resolved_at = $4
            WHERE id = $1
            """,
            conflict_id,
            resolution.value,
            resolved_by,
            datetime.utcnow(),
        )
