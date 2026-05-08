"""
Step 4: Generate testable hypotheses from warn/gap/conflict clusters.
Batches related nodes to minimize Claude calls.
"""
from __future__ import annotations

import json
import uuid

import anthropic

from ...config import settings
from ..models import AnnotatedNode, AnnotationTag, Hypothesis, StepType

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

_SYSTEM = (
    "You generate testable hypotheses for a web application testing agent. "
    "Each hypothesis must be falsifiable and map to a concrete browser or API action."
)


async def generate_hypotheses(
    nodes: list[AnnotatedNode],
    task_description: str,
) -> list[Hypothesis]:
    uncertain = [n for n in nodes if n.annotation in (
        AnnotationTag.GAP, AnnotationTag.WARN, AnnotationTag.CONFLICT
    )]
    confirmed = [n for n in nodes if n.annotation == AnnotationTag.OK]

    hypotheses: list[Hypothesis] = []

    # Confirmed high-confidence nodes → trivial confirm hypothesis
    if confirmed:
        hypotheses.append(
            Hypothesis(
                description=f"Verify {len(confirmed)} high-confidence nodes remain intact",
                node_ids=[n.node_id for n in confirmed],
                expected_outcome="All verified behaviors match current graph knowledge",
                step_type=StepType.CONFIRM,
                confidence=min(n.confidence for n in confirmed),
            )
        )

    if not uncertain:
        return hypotheses

    # Generate hypotheses for uncertain clusters via Claude
    context = [
        {
            "semantic_id": n.semantic_id,
            "definition": n.semantic_definition,
            "layer": n.layer,
            "confidence": n.confidence,
            "annotation": n.annotation.value,
        }
        for n in uncertain
    ]

    tools = [
        {
            "name": "generate_hypotheses",
            "description": "Generate testable hypotheses",
            "input_schema": {
                "type": "object",
                "required": ["hypotheses"],
                "properties": {
                    "hypotheses": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["description", "expected_outcome", "step_type", "node_semantic_ids"],
                            "properties": {
                                "description": {"type": "string"},
                                "expected_outcome": {"type": "string"},
                                "step_type": {
                                    "type": "string",
                                    "enum": ["verify", "discover"],
                                },
                                "node_semantic_ids": {
                                    "type": "array",
                                    "items": {"type": "string"},
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
        max_tokens=1024,
        system=_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Task: {task_description}\n\n"
                    "Generate testable hypotheses for these uncertain/gap nodes:\n"
                    + json.dumps(context, indent=2)
                ),
            }
        ],
        tools=tools,
        tool_choice={"type": "any"},
    )

    node_by_semantic = {n.semantic_id: n for n in uncertain}

    for block in response.content:
        if block.type == "tool_use" and block.name == "generate_hypotheses":
            for h in block.input.get("hypotheses", []):
                node_ids = [
                    node_by_semantic[sid].node_id
                    for sid in h.get("node_semantic_ids", [])
                    if sid in node_by_semantic
                ]
                relevant_nodes = [node_by_semantic[sid] for sid in h.get("node_semantic_ids", []) if sid in node_by_semantic]
                avg_conf = (
                    sum(n.confidence for n in relevant_nodes) / len(relevant_nodes)
                    if relevant_nodes
                    else 50.0
                )
                hypotheses.append(
                    Hypothesis(
                        description=h["description"],
                        node_ids=node_ids,
                        expected_outcome=h["expected_outcome"],
                        step_type=StepType(h["step_type"]),
                        confidence=avg_conf,
                    )
                )

    return hypotheses
