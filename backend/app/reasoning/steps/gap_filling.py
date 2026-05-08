"""
Step 3: For each gap/warn node, infer missing edges via Claude.
Batch related nodes together to minimize API calls.
"""
from __future__ import annotations

import json
import uuid

import anthropic
import asyncpg

from ...config import settings
from ...models.enums import EdgeType, SourceType
from ...models.graph import Edge
from ...db.repositories import EdgeRepository
from ..models import AnnotatedNode, AnnotationTag

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

_SYSTEM = (
    "You are analyzing a knowledge graph for a web application. "
    "Given nodes with missing or uncertain edges, infer what relationships likely exist. "
    "Only infer edges that are strongly implied by the node definitions."
)


async def fill_gaps(
    conn: asyncpg.Connection,
    session_id: uuid.UUID,
    nodes: list[AnnotatedNode],
    all_nodes: list[AnnotatedNode],
) -> list[Edge]:
    """Infer edges for gap/warn nodes. Returns newly created Edge objects."""
    gap_nodes = [n for n in nodes if n.annotation in (AnnotationTag.GAP, AnnotationTag.WARN)]
    if not gap_nodes:
        return []

    # Build lookup by semantic_id
    node_by_id = {n.semantic_id: n for n in all_nodes}
    edge_repo = EdgeRepository(conn)
    inferred: list[Edge] = []

    # Process in batches of 5 to avoid huge prompts
    for i in range(0, len(gap_nodes), 5):
        batch = gap_nodes[i : i + 5]
        context_nodes = [
            {
                "semantic_id": n.semantic_id,
                "definition": n.semantic_definition,
                "layer": n.layer,
                "confidence": n.confidence,
                "existing_edges": n.edges,
                "annotation": n.annotation.value,
            }
            for n in batch
        ]
        neighbor_context = [
            {"semantic_id": n.semantic_id, "definition": n.semantic_definition, "layer": n.layer}
            for n in all_nodes
            if n not in batch
        ][:10]

        edges = await _infer_edges(context_nodes, neighbor_context)

        for e in edges:
            src = node_by_id.get(e["from"])
            tgt = node_by_id.get(e["to"])
            if not src or not tgt:
                continue
            try:
                edge_type = EdgeType(e["edge_type"])
            except ValueError:
                continue
            edge_conf = min(src.confidence, tgt.confidence)
            edge = Edge(
                source_node_id=src.node_id,
                target_node_id=tgt.node_id,
                edge_type=edge_type,
                confidence=edge_conf,
                properties={"inferred": True},
                discovered_in=session_id,
            )
            await edge_repo.insert(edge)
            inferred.append(edge)

    return inferred


async def _infer_edges(
    gap_nodes: list[dict], neighbor_nodes: list[dict]
) -> list[dict]:
    tools = [
        {
            "name": "infer_edges",
            "description": "Infer missing graph edges",
            "input_schema": {
                "type": "object",
                "required": ["edges"],
                "properties": {
                    "edges": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["from", "to", "edge_type"],
                            "properties": {
                                "from": {"type": "string"},
                                "to": {"type": "string"},
                                "edge_type": {
                                    "type": "string",
                                    "enum": [e.value for e in EdgeType],
                                },
                            },
                        },
                    }
                },
            },
        }
    ]

    response = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    "Infer missing edges for these nodes:\n"
                    + json.dumps(gap_nodes, indent=2)
                    + "\n\nNeighbor context:\n"
                    + json.dumps(neighbor_nodes, indent=2)
                ),
            }
        ],
        tools=tools,
        tool_choice={"type": "any"},
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "infer_edges":
            return block.input.get("edges", [])
    return []
