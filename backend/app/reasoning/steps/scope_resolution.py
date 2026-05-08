"""
Step 1: NL task → relevant node set.
Embed the task, cosine-search for seed nodes, BFS expand via causal edges (depth 2).
"""
from __future__ import annotations
import uuid
import asyncpg
from ...services.embeddings import get_embedding


CAUSAL_EDGES = ("triggers", "mutates", "governs", "blocks", "enables")


async def resolve_scope(
    conn: asyncpg.Connection,
    intellion_id: uuid.UUID,
    task: str,
    max_nodes: int = 50,
    traversal_depth: int = 2,
) -> list[dict]:
    """Returns list of node dicts in scope."""
    embedding = await get_embedding(task)

    # Seed: cosine similarity search
    seed_rows = await conn.fetch(
        """
        SELECT id, semantic_id, layer, semantic_definition, confidence, page_path,
               1 - (semantic_embedding <=> $1::vector) AS similarity
        FROM nodes
        WHERE intellion_id = $2 AND status = 'active' AND semantic_embedding IS NOT NULL
        ORDER BY semantic_embedding <=> $1::vector
        LIMIT 20
        """,
        embedding,
        intellion_id,
    )
    seed_ids = [str(r["id"]) for r in seed_rows]

    if not seed_ids:
        return []

    # BFS expansion via recursive CTE
    rows = await conn.fetch(
        f"""
        WITH RECURSIVE subgraph(node_id, depth) AS (
            SELECT id::text, 0
            FROM nodes
            WHERE id = ANY($1::uuid[])

            UNION

            SELECT e.target_node_id::text, sg.depth + 1
            FROM edges e
            JOIN subgraph sg ON e.source_node_id::text = sg.node_id
            WHERE sg.depth < $2
              AND e.edge_type = ANY($3)
        )
        SELECT DISTINCT n.id, n.semantic_id, n.layer, n.semantic_definition,
                        n.confidence, n.page_path, n.verify_due_at, n.status
        FROM subgraph sg
        JOIN nodes n ON n.id = sg.node_id::uuid
        WHERE n.intellion_id = $4
          AND n.status = 'active'
        ORDER BY n.confidence DESC
        LIMIT $5
        """,
        [uuid.UUID(s) for s in seed_ids],
        traversal_depth,
        list(CAUSAL_EDGES),
        intellion_id,
        max_nodes,
    )
    return [dict(r) for r in rows]
