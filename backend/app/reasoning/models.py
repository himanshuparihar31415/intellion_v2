from __future__ import annotations
import uuid
from enum import StrEnum
from typing import Any
from pydantic import BaseModel


class StepType(StrEnum):
    CONFIRM = "confirm"    # high confidence, just verify it hasn't broken
    VERIFY = "verify"      # medium confidence, test the hypothesis
    DISCOVER = "discover"  # gap, no data, go find it


class AnnotationTag(StrEnum):
    OK = "ok"          # confidence >= 70, not expired
    WARN = "warn"      # confidence 40-70 or verify_due_at past
    GAP = "gap"        # missing expected edges for its layer
    CONFLICT = "conflict"  # unresolved conflict exists


class AnnotatedNode(BaseModel):
    node_id: uuid.UUID
    semantic_id: str
    semantic_definition: str
    layer: int
    confidence: float
    page_path: str | None
    annotation: AnnotationTag
    edges: list[str] = []  # "edge_type:target_semantic_id"


class Hypothesis(BaseModel):
    description: str
    node_ids: list[uuid.UUID]
    expected_outcome: str
    step_type: StepType
    confidence: float


class TestStep(BaseModel):
    step_number: int
    description: str
    step_type: StepType
    skill_hint: str  # ui | api | visual
    node_ids: list[uuid.UUID]
    hypothesis: Hypothesis | None = None
    confidence: float
    skip_reason: str | None = None  # set if this step was deduplicated


class TestPlan(BaseModel):
    plan_id: uuid.UUID
    intellion_id: uuid.UUID
    task_description: str
    steps: list[TestStep]
    total_nodes_in_scope: int
    gap_count: int
    conflict_count: int
    estimated_coverage_gain: float


class ReasoningResult(BaseModel):
    plan: TestPlan
    scope_nodes: list[AnnotatedNode]
    hypotheses: list[Hypothesis]
    skipped_node_ids: list[uuid.UUID]
