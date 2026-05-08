from __future__ import annotations
import uuid
import asyncpg
from ...models.graph import Edge
from ...models.enums import EdgeType


class EdgeRepository:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    async def insert(self, edge: Edge) -> Edge:
        await self._conn.execute(
            """
            INSERT INTO edges (
                id, source_node_id, target_node_id, edge_type,
                confidence, properties, discovered_in, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8)
            ON CONFLICT (source_node_id, target_node_id, edge_type) DO NOTHING
            """,
            edge.id,
            edge.source_node_id,
            edge.target_node_id,
            edge.edge_type.value,
            edge.confidence,
            edge.properties,
            edge.discovered_in,
            edge.created_at,
        )
        return edge

    async def get_outbound(
        self,
        node_id: uuid.UUID,
        edge_types: list[EdgeType] | None = None,
    ) -> list[Edge]:
        if edge_types:
            rows = await self._conn.fetch(
                "SELECT * FROM edges WHERE source_node_id = $1 AND edge_type = ANY($2)",
                node_id,
                [e.value for e in edge_types],
            )
        else:
            rows = await self._conn.fetch(
                "SELECT * FROM edges WHERE source_node_id = $1", node_id
            )
        return [Edge(**dict(r)) for r in rows]

    async def get_inbound(self, node_id: uuid.UUID) -> list[Edge]:
        rows = await self._conn.fetch(
            "SELECT * FROM edges WHERE target_node_id = $1", node_id
        )
        return [Edge(**dict(r)) for r in rows]

    async def impact_analysis(
        self, changed_node_id: uuid.UUID, max_depth: int = 5
    ) -> list[dict]:
        """Recursive CTE traversal returning nodes affected by a change."""
        rows = await self._conn.fetch(
            """
            WITH RECURSIVE impact(node_id, depth, path, edge_types) AS (
                SELECT $1::uuid, 0,
                       ARRAY[$1::uuid],
                       ARRAY[]::text[]
                UNION ALL
                SELECT e.target_node_id,
                       i.depth + 1,
                       i.path || e.target_node_id,
                       i.edge_types || e.edge_type
                FROM edges e
                JOIN impact i ON i.node_id = e.source_node_id
                WHERE e.target_node_id != ALL(i.path)
                  AND i.depth < $2
                  AND e.edge_type IN ('triggers','mutates','governs','blocks','enables')
            )
            SELECT DISTINCT n.id, n.semantic_id, n.layer, n.confidence,
                   imp.depth AS hops_from_change,
                   imp.edge_types AS relationship_chain
            FROM impact imp
            JOIN nodes n ON n.id = imp.node_id
            WHERE imp.depth > 0
            ORDER BY imp.depth, n.layer
            """,
            changed_node_id,
            max_depth,
        )
        return [dict(r) for r in rows]
