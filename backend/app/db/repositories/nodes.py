from __future__ import annotations
import uuid
from datetime import datetime, timedelta
import asyncpg
from ...models.graph import Node, NodeSource
from ...models.enums import NodeStatus, Layer, LAYER_VERIFY_DAYS


class NodeRepository:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    async def get(self, node_id: uuid.UUID) -> Node | None:
        row = await self._conn.fetchrow(
            "SELECT * FROM nodes WHERE id = $1", node_id
        )
        return Node(**dict(row)) if row else None

    async def get_by_semantic_id(
        self, intellion_id: uuid.UUID, semantic_id: str
    ) -> Node | None:
        row = await self._conn.fetchrow(
            "SELECT * FROM nodes WHERE intellion_id = $1 AND semantic_id = $2",
            intellion_id,
            semantic_id,
        )
        return Node(**dict(row)) if row else None

    async def find_similar(
        self,
        intellion_id: uuid.UUID,
        embedding: list[float],
        threshold: float = 0.92,
        limit: int = 10,
    ) -> list[tuple[Node, float]]:
        """Cosine similarity search. Returns (node, similarity) pairs."""
        rows = await self._conn.fetch(
            """
            SELECT *, 1 - (semantic_embedding <=> $1::vector) AS similarity
            FROM nodes
            WHERE intellion_id = $2
              AND status = 'active'
              AND semantic_embedding IS NOT NULL
            ORDER BY semantic_embedding <=> $1::vector
            LIMIT $3
            """,
            embedding,
            intellion_id,
            limit,
        )
        results = []
        for row in rows:
            sim = float(row["similarity"])
            if sim >= threshold:
                d = dict(row)
                d.pop("similarity")
                results.append((Node(**d), sim))
        return results

    async def insert(self, node: Node) -> Node:
        await self._conn.execute(
            """
            INSERT INTO nodes (
                id, intellion_id, layer, semantic_id, semantic_definition,
                semantic_embedding, page_path, confidence, confidence_floor,
                status, decay_schedule_days, verify_due_at,
                created_at, updated_at, last_verified_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6::vector, $7, $8, $9, $10, $11, $12, $13, $14, $15
            )
            ON CONFLICT (intellion_id, semantic_id) DO NOTHING
            """,
            node.id,
            node.intellion_id,
            int(node.layer),
            node.semantic_id,
            node.semantic_definition,
            node.semantic_embedding,
            node.page_path,
            node.confidence,
            node.confidence_floor,
            node.status.value,
            node.decay_schedule_days,
            node.verify_due_at,
            node.created_at,
            node.updated_at,
            node.last_verified_at,
        )
        return node

    async def update_confidence(
        self, node_id: uuid.UUID, confidence: float, updated_at: datetime | None = None
    ) -> None:
        await self._conn.execute(
            """
            UPDATE nodes SET confidence = $2, updated_at = $3
            WHERE id = $1
            """,
            node_id,
            confidence,
            updated_at or datetime.utcnow(),
        )

    async def set_verify_due(
        self, node_id: uuid.UUID, due_at: datetime
    ) -> None:
        await self._conn.execute(
            "UPDATE nodes SET verify_due_at = $2 WHERE id = $1",
            node_id,
            due_at,
        )

    async def mark_verified(self, node_id: uuid.UUID) -> None:
        now = datetime.utcnow()
        row = await self._conn.fetchrow("SELECT layer FROM nodes WHERE id = $1", node_id)
        if not row:
            return
        layer = Layer(row["layer"])
        verify_days = LAYER_VERIFY_DAYS[layer]
        await self._conn.execute(
            """
            UPDATE nodes
            SET last_verified_at = $2, verify_due_at = $3, updated_at = $2
            WHERE id = $1
            """,
            node_id,
            now,
            now + timedelta(days=verify_days),
        )

    async def set_status(self, node_id: uuid.UUID, status: NodeStatus) -> None:
        await self._conn.execute(
            "UPDATE nodes SET status = $2, updated_at = now() WHERE id = $1",
            node_id,
            status.value,
        )

    async def list_active(
        self,
        intellion_id: uuid.UUID,
        layer: Layer | None = None,
        page: int = 0,
        page_size: int = 50,
    ) -> list[Node]:
        args: list = [intellion_id, page_size, page * page_size]
        where = "intellion_id = $1 AND status = 'active'"
        if layer is not None:
            where += " AND layer = $4"
            args.append(int(layer))
        rows = await self._conn.fetch(
            f"SELECT * FROM nodes WHERE {where} ORDER BY confidence DESC LIMIT $2 OFFSET $3",
            *args,
        )
        return [Node(**dict(r)) for r in rows]

    async def add_source(self, source: NodeSource) -> None:
        await self._conn.execute(
            """
            INSERT INTO node_sources (
                id, node_id, source_type, source_weight, confidence_delta,
                session_id, document_id, raw_signal_hash,
                extraction_prompt_version, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            source.id,
            source.node_id,
            source.source_type.value,
            source.source_weight,
            source.confidence_delta,
            source.session_id,
            source.document_id,
            source.raw_signal_hash,
            source.extraction_prompt_version,
            source.created_at,
        )

    async def get_sources(self, node_id: uuid.UUID) -> list[NodeSource]:
        rows = await self._conn.fetch(
            "SELECT * FROM node_sources WHERE node_id = $1 ORDER BY created_at",
            node_id,
        )
        return [NodeSource(**dict(r)) for r in rows]
