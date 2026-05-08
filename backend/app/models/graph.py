from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field
from .enums import (
    Layer, SourceType, EdgeType, NodeStatus,
    ConflictSeverity, ConflictResolution, TriggerType,
)


class Node(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    intellion_id: uuid.UUID
    layer: Layer
    semantic_id: str
    semantic_definition: str
    semantic_embedding: list[float] | None = None
    page_path: str | None = None
    confidence: float = Field(ge=0, le=100)
    confidence_floor: float = Field(default=20.0, ge=0, le=100)
    status: NodeStatus = NodeStatus.ACTIVE
    decay_schedule_days: int = 14
    verify_due_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_verified_at: datetime | None = None

    model_config = {"from_attributes": True}


class NodeSource(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    node_id: uuid.UUID
    source_type: SourceType
    source_weight: int
    confidence_delta: float
    session_id: uuid.UUID
    document_id: uuid.UUID | None = None
    raw_signal_hash: str | None = None
    extraction_prompt_version: str = "v1"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}


class Edge(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    edge_type: EdgeType
    confidence: float | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    discovered_in: uuid.UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}


class Conflict(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    intellion_id: uuid.UUID
    node_id: uuid.UUID
    source_a_id: uuid.UUID
    source_b_id: uuid.UUID
    source_a_claim: str
    source_b_claim: str
    weight_gap: int
    severity: ConflictSeverity
    auto_resolvable: bool
    resolution_type: ConflictResolution | None = None
    resolved_by: uuid.UUID | None = None
    resolved_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}


class Intellion(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    target_url: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}


class Session(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    intellion_id: uuid.UUID
    session_type: str  # training | working
    status: str = "active"  # active | completed | failed
    coverage_score: float | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class Document(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    intellion_id: uuid.UUID
    filename: str
    doc_type: str  # pdf | markdown | text
    content_hash: str
    ingested_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}


class DecayEvent(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    trigger_type: TriggerType
    trigger_reference: str
    affected_node_ids: list[uuid.UUID]
    confidence_drop: float
    recomputed_at: datetime = Field(default_factory=datetime.utcnow)
    reverify_queued: bool = False

    model_config = {"from_attributes": True}
