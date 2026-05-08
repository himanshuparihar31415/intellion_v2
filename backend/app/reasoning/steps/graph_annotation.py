"""
Step 2: Tag each node in the subgraph — ok / warn / gap / conflict.
Pure Python, no LLM.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import asyncpg

from ..models import AnnotatedNode, AnnotationTag

# Expected minimum outbound edge counts by layer
_MIN_EDGES: dict[int, int] = {
    1: 0,  # structural: edges not required
    2: 1,  # interaction: should trigger at least one behavior
    3: 0,  # behavioral: may be terminal
    4: 1,  # rule: should govern at least one node
}


async def annotate_nodes(
    conn: asyncpg.Connection,
    intellion_id: uuid.UUID,
    nodes: list[dict],
) -> list[AnnotatedNode]:
    if not nodes:
        return []

    node_ids = [r["id"] for r in nodes]

    # Fetch outbound edge counts
    edge_counts: dict[str, int] = {}
    rows = await conn.fetch(
        "SELECT source_node_id, COUNT(*) AS cnt FROM edges WHERE source_node_id = ANY($1) GROUP BY source_node_id",
        node_ids,
    )
    for row in rows:
        edge_counts[str(row["source_node_id"])] = row["cnt"]

    # Fetch outbound edge summaries
    edge_rows = await conn.fetch(
        "SELECT source_node_id, edge_type, target_node_id FROM edges WHERE source_node_id = ANY($1)",
        node_ids,
    )
    edge_map: dict[str, list[str]] = {}
    for row in edge_rows:
        key = str(row["source_node_id"])
        edge_map.setdefault(key, []).append(row["edge_type"])

    # Fetch unresolved conflict node IDs
    conflict_rows = await conn.fetch(
        """
        SELECT node_id FROM conflicts
        WHERE intellion_id = $1 AND resolution_type IS NULL AND node_id = ANY($2)
        """,
        intellion_id,
        node_ids,
    )
    conflict_node_ids = {str(r["node_id"]) for r in conflict_rows}

    now = datetime.utcnow()
    annotated = []

    for row in nodes:
        nid = str(row["id"])
        confidence = float(row["confidence"])
        layer = int(row["layer"])
        verify_due = row.get("verify_due_at")
        outbound = edge_counts.get(nid, 0)
        edges = edge_map.get(nid, [])

        if nid in conflict_node_ids:
            tag = AnnotationTag.CONFLICT
        elif confidence < 40 or (verify_due and verify_due < now):
            tag = AnnotationTag.WARN
        elif outbound < _MIN_EDGES.get(layer, 0):
            tag = AnnotationTag.GAP
        elif confidence < 70:
            tag = AnnotationTag.WARN
        else:
            tag = AnnotationTag.OK

        annotated.append(
            AnnotatedNode(
                node_id=row["id"],
                semantic_id=row["semantic_id"],
                semantic_definition=row["semantic_definition"],
                layer=layer,
                confidence=confidence,
                page_path=row.get("page_path"),
                annotation=tag,
                edges=edges,
            )
        )

    return annotated
