"""
ReasoningEngine: orchestrates all 5 steps.
  1. scope_resolution  — NL task → node set
  2. graph_annotation  — tag ok/warn/gap/conflict
  3. gap_filling       — infer missing edges
  4. hypothesis_gen    — generate verify/discover/confirm hypotheses
  5. plan_assembly     — order into TestPlan
"""
from __future__ import annotations

import uuid
import asyncpg

from ..config import settings
from .models import AnnotationTag, ReasoningResult
from .steps.scope_resolution import resolve_scope
from .steps.graph_annotation import annotate_nodes
from .steps.gap_filling import fill_gaps
from .steps.hypothesis_gen import generate_hypotheses
from .steps.plan_assembly import assemble_plan


class ReasoningEngine:
    def __init__(self, conn: asyncpg.Connection, session_id: uuid.UUID) -> None:
        self._conn = conn
        self._session_id = session_id

    async def reason(
        self,
        intellion_id: uuid.UUID,
        task: str,
    ) -> ReasoningResult:
        # Step 1: Scope resolution
        scope_rows = await resolve_scope(
            self._conn,
            intellion_id,
            task,
            max_nodes=settings.reasoning_max_subgraph_nodes,
            traversal_depth=settings.reasoning_traversal_depth,
        )

        # Step 2: Graph annotation
        annotated = await annotate_nodes(self._conn, intellion_id, scope_rows)

        # Step 3: Gap filling (infer missing edges)
        await fill_gaps(self._conn, self._session_id, annotated, annotated)

        # Re-annotate after gap filling (edges may have changed)
        annotated = await annotate_nodes(self._conn, intellion_id, scope_rows)

        # Step 4: Hypothesis generation
        hypotheses = await generate_hypotheses(annotated, task)

        gap_count = sum(1 for n in annotated if n.annotation == AnnotationTag.GAP)
        conflict_count = sum(1 for n in annotated if n.annotation == AnnotationTag.CONFLICT)

        # Step 5: Plan assembly
        plan = assemble_plan(
            intellion_id=intellion_id,
            task_description=task,
            hypotheses=hypotheses,
            total_scope_nodes=len(annotated),
            gap_count=gap_count,
            conflict_count=conflict_count,
        )

        return ReasoningResult(
            plan=plan,
            scope_nodes=annotated,
            hypotheses=hypotheses,
            skipped_node_ids=[
                n.node_id for n in annotated if n.annotation == AnnotationTag.OK
            ],
        )
