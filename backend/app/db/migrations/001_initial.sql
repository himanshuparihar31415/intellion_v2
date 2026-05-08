-- Intellion Knowledge Graph — initial schema
-- Requires: pgvector extension

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- ─── Core entities ───────────────────────────────────────────────────────────

CREATE TABLE intellions (
    id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        text NOT NULL,
    target_url  text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sessions (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    intellion_id    uuid NOT NULL REFERENCES intellions(id) ON DELETE CASCADE,
    session_type    text NOT NULL CHECK (session_type IN ('training', 'working')),
    status          text NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'completed', 'failed')),
    coverage_score  numeric(5,2),
    created_at      timestamptz NOT NULL DEFAULT now(),
    completed_at    timestamptz
);

CREATE INDEX idx_sessions_intellion ON sessions(intellion_id);

CREATE TABLE documents (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    intellion_id    uuid NOT NULL REFERENCES intellions(id) ON DELETE CASCADE,
    filename        text NOT NULL,
    doc_type        text NOT NULL CHECK (doc_type IN ('pdf', 'markdown', 'text')),
    content_hash    text NOT NULL,
    ingested_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_documents_intellion ON documents(intellion_id);

-- ─── Knowledge graph ─────────────────────────────────────────────────────────

CREATE TABLE nodes (
    id                  uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    intellion_id        uuid NOT NULL REFERENCES intellions(id) ON DELETE CASCADE,
    layer               smallint NOT NULL CHECK (layer BETWEEN 1 AND 4),
    semantic_id         text NOT NULL,
    semantic_definition text NOT NULL,
    semantic_embedding  vector(1536),
    page_path           text,
    confidence          numeric(5,2) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
    confidence_floor    numeric(5,2) NOT NULL DEFAULT 20.0,
    status              text NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'decayed', 'archived', 'conflicted')),
    decay_schedule_days smallint NOT NULL DEFAULT 14,
    verify_due_at       timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    last_verified_at    timestamptz,
    UNIQUE (intellion_id, semantic_id)
);

CREATE INDEX idx_nodes_intellion_status  ON nodes(intellion_id, status);
CREATE INDEX idx_nodes_layer             ON nodes(layer);
CREATE INDEX idx_nodes_page_path         ON nodes(page_path text_pattern_ops);
CREATE INDEX idx_nodes_confidence        ON nodes(confidence);
CREATE INDEX idx_nodes_verify_due        ON nodes(verify_due_at);
CREATE INDEX idx_nodes_updated           ON nodes(updated_at);
CREATE INDEX idx_nodes_last_verified     ON nodes(last_verified_at);
-- NOTE: IVFFlat embedding index created separately after 10k rows via:
-- CREATE INDEX CONCURRENTLY idx_nodes_embedding ON nodes
--   USING ivfflat (semantic_embedding vector_cosine_ops) WITH (lists = 100);

CREATE TABLE node_sources (
    id                       uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    node_id                  uuid NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    source_type              text NOT NULL
                                 CHECK (source_type IN (
                                     'exploration','document','human',
                                     'schema','test_execution','inference'
                                 )),
    source_weight            smallint NOT NULL,
    confidence_delta         numeric(5,2) NOT NULL,
    session_id               uuid NOT NULL REFERENCES sessions(id),
    document_id              uuid REFERENCES documents(id),
    raw_signal_hash          text,
    extraction_prompt_version text NOT NULL DEFAULT 'v1',
    created_at               timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_node_sources_node    ON node_sources(node_id);
CREATE INDEX idx_node_sources_session ON node_sources(session_id);
CREATE INDEX idx_node_sources_type    ON node_sources(source_type);
CREATE INDEX idx_node_sources_created ON node_sources(created_at);

CREATE TABLE edges (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_node_id  uuid NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    target_node_id  uuid NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    edge_type       text NOT NULL CHECK (edge_type IN (
                        'triggers','mutates','governs','parent_of','sibling_of',
                        'blocks','enables','references','conflicts_with',
                        'supersedes','accessible_only_if'
                    )),
    confidence      numeric(5,2),
    properties      jsonb NOT NULL DEFAULT '{}',
    discovered_in   uuid NOT NULL REFERENCES sessions(id),
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_node_id, target_node_id, edge_type)
);

CREATE INDEX idx_edges_source ON edges(source_node_id, edge_type);
CREATE INDEX idx_edges_target ON edges(target_node_id, edge_type);

-- Auto-recompute edge confidence when either endpoint changes
CREATE OR REPLACE FUNCTION recompute_edge_confidence()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    UPDATE edges SET confidence = (
        SELECT LEAST(n1.confidence, n2.confidence)
        FROM nodes n1, nodes n2
        WHERE n1.id = edges.source_node_id
          AND n2.id = edges.target_node_id
    )
    WHERE source_node_id = NEW.id OR target_node_id = NEW.id;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_node_confidence_update
AFTER UPDATE OF confidence ON nodes
FOR EACH ROW EXECUTE FUNCTION recompute_edge_confidence();

CREATE TABLE conflicts (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    intellion_id    uuid NOT NULL REFERENCES intellions(id) ON DELETE CASCADE,
    node_id         uuid NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    source_a_id     uuid NOT NULL REFERENCES node_sources(id),
    source_b_id     uuid NOT NULL REFERENCES node_sources(id),
    source_a_claim  text NOT NULL,
    source_b_claim  text NOT NULL,
    weight_gap      smallint NOT NULL,
    severity        text NOT NULL CHECK (severity IN ('critical','high','medium','low')),
    auto_resolvable boolean NOT NULL DEFAULT false,
    resolution_type text CHECK (resolution_type IN (
                        'winner_a','winner_b','both_wrong','intentional'
                    )),
    resolved_by     uuid,
    resolved_at     timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_conflicts_intellion_resolution ON conflicts(intellion_id, resolution_type);
CREATE INDEX idx_conflicts_node                 ON conflicts(node_id);
CREATE INDEX idx_conflicts_severity             ON conflicts(severity, auto_resolvable);
CREATE INDEX idx_conflicts_created              ON conflicts(created_at);

-- ─── Decay tracking ──────────────────────────────────────────────────────────

CREATE TABLE decay_events (
    id                  uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    trigger_type        text NOT NULL CHECK (trigger_type IN (
                            'frontend_deploy','api_schema_change',
                            'document_update','time_decay','manual'
                        )),
    trigger_reference   text NOT NULL,
    affected_node_ids   uuid[] NOT NULL DEFAULT '{}',
    confidence_drop     numeric(5,2) NOT NULL,
    recomputed_at       timestamptz NOT NULL DEFAULT now(),
    reverify_queued     boolean NOT NULL DEFAULT false
);

CREATE INDEX idx_decay_events_recomputed ON decay_events(recomputed_at);

-- ─── Training frontier ───────────────────────────────────────────────────────

CREATE TABLE frontier_items (
    id                  uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    intellion_id        uuid NOT NULL REFERENCES intellions(id) ON DELETE CASCADE,
    target_description  text NOT NULL,
    target_node_id      uuid REFERENCES nodes(id),
    created_by_source   text NOT NULL CHECK (created_by_source IN ('exploration','document','manual')),
    gap_weight          numeric(5,2) NOT NULL DEFAULT 50.0,
    status              text NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending','in_progress','done','skipped')),
    last_attempted_at   timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_frontier_intellion_status  ON frontier_items(intellion_id, status);
CREATE INDEX idx_frontier_last_attempted    ON frontier_items(last_attempted_at);
