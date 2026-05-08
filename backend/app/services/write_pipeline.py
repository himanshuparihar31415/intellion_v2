"""
4-stage NodeWritePipeline: signal capture → semantic extraction →
node resolution (dedup) → graph write with provenance.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import anthropic
import asyncpg

from ..config import settings
from ..db.repositories import EdgeRepository, NodeRepository
from ..models.enums import (
    SOURCE_BASE_CONFIDENCE,
    SOURCE_WEIGHTS,
    LAYER_VERIFY_DAYS,
    ConflictSeverity,
    EdgeType,
    Layer,
    NodeStatus,
    SourceType,
)
from ..models.graph import Conflict, Edge, Node, NodeSource
from .embeddings import get_embedding

_anthropic = anthropic.Anthropic(api_key=settings.anthropic_api_key)

# Cached system prompt for extraction calls
_EXTRACTION_SYSTEM = (
    "You are a knowledge-graph extraction engine for web applications. "
    "Given a raw signal bundle (DOM delta, network trace, page context) "
    "you extract structured knowledge nodes and relationships. "
    "Be precise and conservative — only assert what the signal directly evidences."
)


@dataclass
class RawSignal:
    """Stage 1 output — everything captured around a single page interaction."""
    page_url: str
    page_path: str
    action_type: str  # click | fill | navigate | observe
    action_selector: str | None
    dom_delta: dict[str, Any]       # changed, added, removed elements
    network_trace: list[dict]       # XHR/fetch records
    visual_diff_summary: str | None = None
    existing_graph_context: str = ""  # JSON summary of known nodes on this page


@dataclass
class NodeCandidate:
    semantic_id: str
    layer: Layer
    semantic_definition: str
    page_path: str | None
    confidence_base: float
    source_type: SourceType


@dataclass
class EdgeCandidate:
    from_semantic_id: str
    to_semantic_id: str
    edge_type: EdgeType


@dataclass
class ExtractionResult:
    node_candidates: list[NodeCandidate] = field(default_factory=list)
    edge_candidates: list[EdgeCandidate] = field(default_factory=list)
    conflict_flags: list[str] = field(default_factory=list)


class NodeWritePipeline:
    """
    Stages:
      1. signal_capture  — already done by caller; this receives a RawSignal
      2. semantic_extraction — Claude LLM call → ExtractionResult
      3. node_resolution  — dedup via cosine similarity + confidence merge
      4. graph_write      — persist nodes, sources, edges, queue re-verify
    """

    def __init__(
        self,
        conn: asyncpg.Connection,
        intellion_id: uuid.UUID,
        session_id: uuid.UUID,
        source_type: SourceType = SourceType.EXPLORATION,
    ) -> None:
        self._conn = conn
        self._intellion_id = intellion_id
        self._session_id = session_id
        self._source_type = source_type
        self._nodes = NodeRepository(conn)
        self._edges = EdgeRepository(conn)

    # ── Stage 2: Semantic extraction ─────────────────────────────────────────

    async def extract(self, signal: RawSignal) -> ExtractionResult:
        prompt_content = json.dumps(
            {
                "page_url": signal.page_url,
                "action": {
                    "type": signal.action_type,
                    "selector": signal.action_selector,
                },
                "dom_delta": signal.dom_delta,
                "network_trace": signal.network_trace,
                "visual_diff": signal.visual_diff_summary,
                "existing_graph_context": signal.existing_graph_context,
            },
            indent=2,
        )

        tools = [
            {
                "name": "record_knowledge",
                "description": "Record extracted knowledge nodes and relationships",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "node_candidates": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["semantic_id", "layer", "semantic_definition"],
                                "properties": {
                                    "semantic_id": {"type": "string"},
                                    "layer": {"type": "integer", "enum": [1, 2, 3, 4]},
                                    "semantic_definition": {"type": "string"},
                                    "page_path": {"type": "string"},
                                    "confidence_base": {"type": "number"},
                                },
                            },
                        },
                        "edge_candidates": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["from_semantic_id", "to_semantic_id", "edge_type"],
                                "properties": {
                                    "from_semantic_id": {"type": "string"},
                                    "to_semantic_id": {"type": "string"},
                                    "edge_type": {
                                        "type": "string",
                                        "enum": [e.value for e in EdgeType],
                                    },
                                },
                            },
                        },
                        "conflict_flags": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["node_candidates", "edge_candidates", "conflict_flags"],
                },
            }
        ]

        response = _anthropic.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=_EXTRACTION_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Extract knowledge nodes and relationships from this signal bundle:\n\n"
                        + prompt_content
                    ),
                }
            ],
            tools=tools,
            tool_choice={"type": "any"},
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "record_knowledge":
                data = block.input
                base_conf = SOURCE_BASE_CONFIDENCE[self._source_type]
                return ExtractionResult(
                    node_candidates=[
                        NodeCandidate(
                            semantic_id=n["semantic_id"],
                            layer=Layer(n["layer"]),
                            semantic_definition=n["semantic_definition"],
                            page_path=n.get("page_path", signal.page_path),
                            confidence_base=n.get("confidence_base", base_conf),
                            source_type=self._source_type,
                        )
                        for n in data.get("node_candidates", [])
                    ],
                    edge_candidates=[
                        EdgeCandidate(
                            from_semantic_id=e["from_semantic_id"],
                            to_semantic_id=e["to_semantic_id"],
                            edge_type=EdgeType(e["edge_type"]),
                        )
                        for e in data.get("edge_candidates", [])
                    ],
                    conflict_flags=data.get("conflict_flags", []),
                )

        return ExtractionResult()

    # ── Stage 3: Node resolution + confidence merge ───────────────────────────

    async def resolve_node(
        self, candidate: NodeCandidate, raw_signal_hash: str
    ) -> tuple[Node, float]:
        """
        Returns (node, confidence_delta).
        - If new: inserts with base confidence.
        - If existing and consistent: merges using weighted-average confidence.
        - If existing and conflicting: drops confidence, opens conflict record.
        """
        embedding = await get_embedding(candidate.semantic_definition)
        existing = await self._nodes.get_by_semantic_id(
            self._intellion_id, candidate.semantic_id
        )

        if existing is None:
            # Check embedding similarity for fuzzy dedup
            similar = await self._nodes.find_similar(
                self._intellion_id,
                embedding,
                threshold=settings.dedup_similarity_threshold,
                limit=1,
            )
            if similar:
                existing, _ = similar[0]

        source_weight = SOURCE_WEIGHTS[self._source_type]
        now = datetime.utcnow()

        if existing is None:
            # Path A: New node
            verify_days = LAYER_VERIFY_DAYS[candidate.layer]
            node = Node(
                intellion_id=self._intellion_id,
                layer=candidate.layer,
                semantic_id=candidate.semantic_id,
                semantic_definition=candidate.semantic_definition,
                semantic_embedding=embedding,
                page_path=candidate.page_path,
                confidence=candidate.confidence_base,
                decay_schedule_days=verify_days,
                verify_due_at=now + timedelta(days=verify_days),
                created_at=now,
                updated_at=now,
            )
            await self._nodes.insert(node)
            return node, candidate.confidence_base

        # Path B: Merge — weighted-average confidence update
        old_conf = float(existing.confidence)
        old_weight = SOURCE_WEIGHTS.get(SourceType.EXPLORATION, 0.6)
        new_conf = candidate.confidence_base
        merged = (old_conf * old_weight + new_conf * source_weight) / (old_weight + source_weight)
        merged = min(100.0, merged)
        delta = merged - old_conf

        await self._nodes.update_confidence(existing.id, merged, now)
        existing.confidence = merged
        return existing, delta

    # ── Stage 4: Full pipeline entry point ────────────────────────────────────

    async def process(self, signal: RawSignal) -> list[Node]:
        """Run all 4 stages. Returns list of written/updated nodes."""
        raw_hash = hashlib.sha256(
            json.dumps({"url": signal.page_url, "dom": signal.dom_delta}).encode()
        ).hexdigest()

        extraction = await self.extract(signal)
        written_nodes: dict[str, Node] = {}

        for candidate in extraction.node_candidates:
            node, delta = await self.resolve_node(candidate, raw_hash)
            written_nodes[candidate.semantic_id] = node

            # Append-only source record
            source = NodeSource(
                node_id=node.id,
                source_type=self._source_type,
                source_weight=int(SOURCE_WEIGHTS[self._source_type] * 100),
                confidence_delta=delta,
                session_id=self._session_id,
                raw_signal_hash=raw_hash,
            )
            await self._nodes.add_source(source)

        # Write edges between known nodes
        for ec in extraction.edge_candidates:
            src = written_nodes.get(ec.from_semantic_id)
            tgt = written_nodes.get(ec.to_semantic_id)
            if src and tgt:
                edge_conf = min(src.confidence, tgt.confidence)
                edge = Edge(
                    source_node_id=src.id,
                    target_node_id=tgt.id,
                    edge_type=ec.edge_type,
                    confidence=edge_conf,
                    discovered_in=self._session_id,
                )
                await self._edges.insert(edge)

        return list(written_nodes.values())

    # ── Convenience: ingest a plain fact (document / human teach) ─────────────

    async def ingest_fact(
        self,
        semantic_id: str,
        semantic_definition: str,
        layer: Layer,
        page_path: str | None = None,
        confidence_override: float | None = None,
        document_id: uuid.UUID | None = None,
    ) -> Node:
        """Directly write a node from a document or human teacher, bypassing extraction."""
        base_conf = confidence_override or SOURCE_BASE_CONFIDENCE[self._source_type]
        embedding = await get_embedding(semantic_definition)
        now = datetime.utcnow()
        verify_days = LAYER_VERIFY_DAYS[layer]

        existing = await self._nodes.get_by_semantic_id(self._intellion_id, semantic_id)

        if existing is None:
            similar = await self._nodes.find_similar(
                self._intellion_id,
                embedding,
                threshold=settings.dedup_similarity_threshold,
                limit=1,
            )
            if similar:
                existing, _ = similar[0]

        source_weight = SOURCE_WEIGHTS[self._source_type]

        if existing is None:
            node = Node(
                intellion_id=self._intellion_id,
                layer=layer,
                semantic_id=semantic_id,
                semantic_definition=semantic_definition,
                semantic_embedding=embedding,
                page_path=page_path,
                confidence=base_conf,
                decay_schedule_days=verify_days,
                verify_due_at=now + timedelta(days=verify_days),
                created_at=now,
                updated_at=now,
            )
            await self._nodes.insert(node)
            delta = base_conf
        else:
            old_conf = float(existing.confidence)
            old_weight = SOURCE_WEIGHTS.get(SourceType.EXPLORATION, 0.6)
            merged = min(100.0, (old_conf * old_weight + base_conf * source_weight) / (old_weight + source_weight))
            delta = merged - old_conf
            await self._nodes.update_confidence(existing.id, merged, now)
            existing.confidence = merged
            node = existing

        source = NodeSource(
            node_id=node.id,
            source_type=self._source_type,
            source_weight=int(source_weight * 100),
            confidence_delta=delta,
            session_id=self._session_id,
            document_id=document_id,
        )
        await self._nodes.add_source(source)
        return node
