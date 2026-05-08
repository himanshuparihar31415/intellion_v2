from enum import IntEnum, StrEnum


class Layer(IntEnum):
    STRUCTURAL = 1
    INTERACTION = 2
    BEHAVIORAL = 3
    RULE = 4


class SourceType(StrEnum):
    EXPLORATION = "exploration"
    DOCUMENT = "document"
    HUMAN = "human"
    SCHEMA = "schema"
    TEST_EXECUTION = "test_execution"
    INFERENCE = "inference"


SOURCE_WEIGHTS: dict[SourceType, float] = {
    SourceType.HUMAN: 1.0,
    SourceType.TEST_EXECUTION: 0.9,
    SourceType.SCHEMA: 0.8,
    SourceType.DOCUMENT: 0.7,
    SourceType.EXPLORATION: 0.6,
    SourceType.INFERENCE: 0.5,
}

SOURCE_BASE_CONFIDENCE: dict[SourceType, float] = {
    SourceType.HUMAN: 95.0,
    SourceType.TEST_EXECUTION: 90.0,
    SourceType.SCHEMA: 78.0,
    SourceType.DOCUMENT: 72.0,
    SourceType.EXPLORATION: 60.0,
    SourceType.INFERENCE: 42.0,
}


class EdgeType(StrEnum):
    TRIGGERS = "triggers"
    MUTATES = "mutates"
    GOVERNS = "governs"
    PARENT_OF = "parent_of"
    SIBLING_OF = "sibling_of"
    BLOCKS = "blocks"
    ENABLES = "enables"
    REFERENCES = "references"
    CONFLICTS_WITH = "conflicts_with"
    SUPERSEDES = "supersedes"
    ACCESSIBLE_ONLY_IF = "accessible_only_if"


class NodeStatus(StrEnum):
    ACTIVE = "active"
    DECAYED = "decayed"
    ARCHIVED = "archived"
    CONFLICTED = "conflicted"


class ConflictSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ConflictResolution(StrEnum):
    WINNER_A = "winner_a"
    WINNER_B = "winner_b"
    BOTH_WRONG = "both_wrong"
    INTENTIONAL = "intentional"


class TriggerType(StrEnum):
    FRONTEND_DEPLOY = "frontend_deploy"
    API_SCHEMA_CHANGE = "api_schema_change"
    DOCUMENT_UPDATE = "document_update"
    TIME_DECAY = "time_decay"
    MANUAL = "manual"


# Re-verify intervals in days by layer
LAYER_VERIFY_DAYS: dict[Layer, int] = {
    Layer.STRUCTURAL: 14,
    Layer.INTERACTION: 7,
    Layer.BEHAVIORAL: 5,
    Layer.RULE: 30,
}

# Decay schedule start (days since last verify before decay begins)
LAYER_DECAY_START_DAYS: dict[Layer, int] = {
    Layer.STRUCTURAL: 30,
    Layer.INTERACTION: 21,
    Layer.BEHAVIORAL: 14,
    Layer.RULE: 60,
}
