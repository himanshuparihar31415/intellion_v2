"""
Integration tests for NodeWritePipeline.

Requires running PostgreSQL + pgvector. Run with:
  DATABASE_URL=postgresql://... pytest tests/test_write_pipeline.py -v

The tests mock the LLM and embedding calls to avoid API costs in CI.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.repositories import EdgeRepository, NodeRepository
from app.models.enums import EdgeType, Layer, SourceType
from app.services.write_pipeline import (
    EdgeCandidate,
    ExtractionResult,
    NodeCandidate,
    NodeWritePipeline,
    RawSignal,
)


def make_signal(page_path: str = "/product/1") -> RawSignal:
    return RawSignal(
        page_url=f"http://localhost:3000{page_path}",
        page_path=page_path,
        action_type="click",
        action_selector="#btn-add-cart",
        dom_delta={
            "changed": ["#cart-badge: 0→1"],
            "added": ["#toast-added"],
            "removed": [],
        },
        network_trace=[
            {
                "method": "POST",
                "url": "/api/cart",
                "response": {"status": 200},
            }
        ],
    )


MOCK_EXTRACTION = ExtractionResult(
    node_candidates=[
        NodeCandidate(
            semantic_id="btn_add_to_cart",
            layer=Layer.INTERACTION,
            semantic_definition="Add to cart button — POSTs item_id to /api/cart",
            page_path="/product/:id",
            confidence_base=62.0,
            source_type=SourceType.EXPLORATION,
        ),
        NodeCandidate(
            semantic_id="behavior_cart_badge_increment",
            layer=Layer.BEHAVIORAL,
            semantic_definition="Cart badge count increments by 1 after add-to-cart",
            page_path="/product/:id",
            confidence_base=58.0,
            source_type=SourceType.EXPLORATION,
        ),
    ],
    edge_candidates=[
        EdgeCandidate(
            from_semantic_id="btn_add_to_cart",
            to_semantic_id="behavior_cart_badge_increment",
            edge_type=EdgeType.TRIGGERS,
        )
    ],
    conflict_flags=[],
)

MOCK_EMBEDDING = [0.1] * 1536


@pytest.fixture
def pipeline(conn, intellion_id, session_id):
    return NodeWritePipeline(
        conn=conn,
        intellion_id=intellion_id,
        session_id=session_id,
        source_type=SourceType.EXPLORATION,
    )


@pytest.mark.asyncio
async def test_write_pipeline_creates_nodes(pipeline, conn, intellion_id):
    """Processing a signal creates the expected nodes in the DB."""
    with (
        patch.object(pipeline, "extract", new=AsyncMock(return_value=MOCK_EXTRACTION)),
        patch(
            "app.services.write_pipeline.get_embedding",
            new=AsyncMock(return_value=MOCK_EMBEDDING),
        ),
    ):
        nodes = await pipeline.process(make_signal())

    assert len(nodes) == 2
    semantic_ids = {n.semantic_id for n in nodes}
    assert "btn_add_to_cart" in semantic_ids
    assert "behavior_cart_badge_increment" in semantic_ids

    node_repo = NodeRepository(conn)
    btn = await node_repo.get_by_semantic_id(intellion_id, "btn_add_to_cart")
    assert btn is not None
    assert btn.layer == Layer.INTERACTION
    assert btn.confidence == pytest.approx(62.0, abs=1.0)
    assert btn.semantic_embedding is not None


@pytest.mark.asyncio
async def test_write_pipeline_stores_embedding(pipeline, conn, intellion_id):
    """Nodes written by the pipeline have embeddings stored."""
    with (
        patch.object(pipeline, "extract", new=AsyncMock(return_value=MOCK_EXTRACTION)),
        patch(
            "app.services.write_pipeline.get_embedding",
            new=AsyncMock(return_value=MOCK_EMBEDDING),
        ),
    ):
        nodes = await pipeline.process(make_signal())

    node_repo = NodeRepository(conn)
    for node in nodes:
        row = await conn.fetchrow("SELECT semantic_embedding FROM nodes WHERE id = $1", node.id)
        assert row is not None
        assert row["semantic_embedding"] is not None


@pytest.mark.asyncio
async def test_write_pipeline_creates_edge(pipeline, conn, intellion_id):
    """An edge is written between the two extracted nodes."""
    with (
        patch.object(pipeline, "extract", new=AsyncMock(return_value=MOCK_EXTRACTION)),
        patch(
            "app.services.write_pipeline.get_embedding",
            new=AsyncMock(return_value=MOCK_EMBEDDING),
        ),
    ):
        nodes = await pipeline.process(make_signal())

    btn = next(n for n in nodes if n.semantic_id == "btn_add_to_cart")
    behavior = next(n for n in nodes if n.semantic_id == "behavior_cart_badge_increment")

    edge_row = await conn.fetchrow(
        "SELECT * FROM edges WHERE source_node_id = $1 AND target_node_id = $2",
        btn.id,
        behavior.id,
    )
    assert edge_row is not None
    assert edge_row["edge_type"] == "triggers"


@pytest.mark.asyncio
async def test_write_pipeline_source_audit_trail(pipeline, conn, intellion_id, session_id):
    """Each node written has an append-only source record."""
    with (
        patch.object(pipeline, "extract", new=AsyncMock(return_value=MOCK_EXTRACTION)),
        patch(
            "app.services.write_pipeline.get_embedding",
            new=AsyncMock(return_value=MOCK_EMBEDDING),
        ),
    ):
        nodes = await pipeline.process(make_signal())

    node_repo = NodeRepository(conn)
    for node in nodes:
        sources = await node_repo.get_sources(node.id)
        assert len(sources) >= 1
        assert sources[0].session_id == session_id
        assert sources[0].source_type == SourceType.EXPLORATION


@pytest.mark.asyncio
async def test_write_pipeline_deduplicates_on_reprocess(pipeline, conn, intellion_id):
    """Re-processing the same signal merges confidence instead of creating duplicates."""
    with (
        patch.object(pipeline, "extract", new=AsyncMock(return_value=MOCK_EXTRACTION)),
        patch(
            "app.services.write_pipeline.get_embedding",
            new=AsyncMock(return_value=MOCK_EMBEDDING),
        ),
    ):
        await pipeline.process(make_signal())
        await pipeline.process(make_signal())

    count = await conn.fetchval(
        "SELECT COUNT(*) FROM nodes WHERE intellion_id = $1 AND semantic_id = $2",
        intellion_id,
        "btn_add_to_cart",
    )
    assert count == 1  # not 2


@pytest.mark.asyncio
async def test_ingest_fact_creates_node(pipeline, conn, intellion_id):
    """ingest_fact writes a node directly without LLM extraction."""
    with patch(
        "app.services.write_pipeline.get_embedding",
        new=AsyncMock(return_value=MOCK_EMBEDDING),
    ):
        node = await pipeline.ingest_fact(
            semantic_id="rule_admin_timeout",
            semantic_definition="Admin sessions time out after 15 minutes of inactivity",
            layer=Layer.RULE,
            confidence_override=95.0,
        )

    assert node.semantic_id == "rule_admin_timeout"
    assert node.confidence == pytest.approx(95.0, abs=0.1)
    assert node.layer == Layer.RULE
