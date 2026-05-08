"""
Step 5: Order hypotheses into an executable TestPlan.
Ordering: confirm first (smoke test), then verify, then discover.
"""
from __future__ import annotations

import uuid
from ..models import Hypothesis, StepType, TestPlan, TestStep


def assemble_plan(
    intellion_id: uuid.UUID,
    task_description: str,
    hypotheses: list[Hypothesis],
    total_scope_nodes: int,
    gap_count: int,
    conflict_count: int,
) -> TestPlan:
    # Sort: confirm → verify → discover
    ordered = sorted(
        hypotheses,
        key=lambda h: {"confirm": 0, "verify": 1, "discover": 2}[h.step_type.value],
    )

    steps: list[TestStep] = []
    for i, hypo in enumerate(ordered, start=1):
        skill = _infer_skill(hypo)
        steps.append(
            TestStep(
                step_number=i,
                description=hypo.description,
                step_type=hypo.step_type,
                skill_hint=skill,
                node_ids=hypo.node_ids,
                hypothesis=hypo,
                confidence=hypo.confidence,
            )
        )

    estimated_gain = min(100.0, gap_count * 15.0 + conflict_count * 5.0)

    return TestPlan(
        plan_id=uuid.uuid4(),
        intellion_id=intellion_id,
        task_description=task_description,
        steps=steps,
        total_nodes_in_scope=total_scope_nodes,
        gap_count=gap_count,
        conflict_count=conflict_count,
        estimated_coverage_gain=estimated_gain,
    )


def _infer_skill(hypo: Hypothesis) -> str:
    desc = hypo.description.lower()
    if "api" in desc or "endpoint" in desc or "http" in desc:
        return "api"
    if "visual" in desc or "screenshot" in desc or "layout" in desc:
        return "visual"
    return "ui"
