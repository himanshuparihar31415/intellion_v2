"""
GraphSyncService: write mission findings back to the knowledge graph.
- confirmed → confidence +5
- logic_deviation → open conflict record, confidence -10
- discovery → new node at confidence 60
"""
from __future__ import annotations

import uuid
from datetime import datetime

import asyncpg

from ..db.repositories import NodeRepository
from ..models.enums import ConflictSeverity, NodeStatus, SourceType
from ..models.graph import Conflict, NodeSource
from ..services.write_pipeline import NodeWritePipeline
from .findings import Finding, FindingType


class GraphSyncService:
    def __init__(
        self,
        conn: asyncpg.Connection,
        intellion_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> None:
        self._conn = conn
        self._intellion_id = intellion_id
        self._session_id = session_id
        self._nodes = NodeRepository(conn)

    async def sync(self, findings: list[Finding]) -> dict:
        confirmed = 0
        deviations = 0
        discoveries = 0

        for finding in findings:
            if finding.finding_type == FindingType.CONFIRMED:
                await self._handle_confirmed(finding)
                confirmed += 1
            elif finding.finding_type == FindingType.LOGIC_DEVIATION:
                await self._handle_deviation(finding)
                deviations += 1
            elif finding.finding_type == FindingType.DISCOVERY:
                await self._handle_discovery(finding)
                discoveries += 1

        return {"confirmed": confirmed, "deviations": deviations, "discoveries": discoveries}

    async def _handle_confirmed(self, finding: Finding) -> None:
        for node_id in finding.node_ids_affected:
            node = await self._nodes.get(node_id)
            if not node:
                continue
            new_conf = min(100.0, float(node.confidence) + 5.0)
            await self._nodes.update_confidence(node_id, new_conf)
            await self._nodes.mark_verified(node_id)
            source = NodeSource(
                node_id=node_id,
                source_type=SourceType.TEST_EXECUTION,
                source_weight=90,
                confidence_delta=5.0,
                session_id=self._session_id,
            )
            await self._nodes.add_source(source)

    async def _handle_deviation(self, finding: Finding) -> None:
        for node_id in finding.node_ids_affected:
            node = await self._nodes.get(node_id)
            if not node:
                continue
            new_conf = max(0.0, float(node.confidence) - 10.0)
            await self._nodes.update_confidence(node_id, new_conf)
            await self._nodes.set_status(node_id, NodeStatus.CONFLICTED)

            # Open a conflict record
            source = NodeSource(
                node_id=node_id,
                source_type=SourceType.TEST_EXECUTION,
                source_weight=90,
                confidence_delta=-10.0,
                session_id=self._session_id,
            )
            await self._nodes.add_source(source)

            # Find the most recent prior source for this node
            sources = await self._nodes.get_sources(node_id)
            prior_source = next(
                (s for s in reversed(sources) if s.source_type != SourceType.TEST_EXECUTION),
                None,
            )
            if prior_source:
                weight_gap = abs(90 - prior_source.source_weight)
                severity = (
                    ConflictSeverity.HIGH if weight_gap >= 25 else ConflictSeverity.MEDIUM
                )
                conflict = Conflict(
                    intellion_id=self._intellion_id,
                    node_id=node_id,
                    source_a_id=prior_source.id,
                    source_b_id=source.id,
                    source_a_claim=node.semantic_definition,
                    source_b_claim=finding.description,
                    weight_gap=weight_gap,
                    severity=severity,
                    auto_resolvable=weight_gap >= 25,
                )
                await self._conn.execute(
                    """
                    INSERT INTO conflicts (
                        id, intellion_id, node_id, source_a_id, source_b_id,
                        source_a_claim, source_b_claim, weight_gap, severity,
                        auto_resolvable, created_at
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
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
                    conflict.created_at,
                )

    async def _handle_discovery(self, finding: Finding) -> None:
        # Discoveries are written back through the write pipeline
        # The raw_output may contain enough context to create a new node
        pipeline = NodeWritePipeline(
            self._conn,
            self._intellion_id,
            self._session_id,
            source_type=SourceType.TEST_EXECUTION,
        )
        desc = finding.description
        if len(desc) > 20:
            from ..models.enums import Layer
            await pipeline.ingest_fact(
                semantic_id=f"discovery_{uuid.uuid4().hex[:8]}",
                semantic_definition=desc,
                layer=Layer.BEHAVIORAL,
                confidence_override=60.0,
            )
