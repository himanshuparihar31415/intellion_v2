"""
MesoLoopService: cross-session pattern extraction.
Analyzes completed sessions to find patterns and adjust frontier weights.
Does NOT write to the graph — only produces session analytics.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import asyncpg


async def extract_session_patterns(
    conn: asyncpg.Connection,
    intellion_id: uuid.UUID,
    lookback_days: int = 30,
) -> dict:
    since = datetime.utcnow() - timedelta(days=lookback_days)

    # Which node layers generate the most logic_deviation findings?
    # (Approximated by confidence drops in completed sessions)
    high_decay_layers = await conn.fetch(
        """
        SELECT n.layer, COUNT(*) AS drop_count, AVG(ns.confidence_delta) AS avg_drop
        FROM node_sources ns
        JOIN nodes n ON n.id = ns.node_id
        JOIN sessions s ON s.id = ns.session_id
        WHERE n.intellion_id = $1
          AND s.session_type = 'working'
          AND s.status = 'completed'
          AND s.created_at > $2
          AND ns.confidence_delta < 0
        GROUP BY n.layer
        ORDER BY avg_drop ASC
        """,
        intellion_id,
        since,
    )

    # Which frontier items were most productive (led to new nodes)?
    discovery_rate = await conn.fetchval(
        """
        SELECT COUNT(*)
        FROM node_sources ns
        JOIN sessions s ON s.id = ns.session_id
        WHERE ns.node_id IN (
            SELECT id FROM nodes WHERE intellion_id = $1
        )
        AND s.session_type = 'working'
        AND s.created_at > $2
        AND ns.source_type = 'test_execution'
        """,
        intellion_id,
        since,
    )

    # Coverage score trend
    coverage_trend = await conn.fetch(
        """
        SELECT coverage_score, created_at
        FROM sessions
        WHERE intellion_id = $1 AND session_type = 'training' AND coverage_score IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 10
        """,
        intellion_id,
    )

    return {
        "period_days": lookback_days,
        "high_decay_layers": [
            {"layer": r["layer"], "drop_count": r["drop_count"], "avg_drop": float(r["avg_drop"])}
            for r in high_decay_layers
        ],
        "working_discoveries": discovery_rate or 0,
        "coverage_trend": [
            {"coverage": float(r["coverage_score"]), "at": r["created_at"].isoformat()}
            for r in coverage_trend
        ],
        "recommendation": _recommend(high_decay_layers),
    }


def _recommend(decay_rows) -> str:
    if not decay_rows:
        return "Insufficient data for recommendations."
    worst_layer = max(decay_rows, key=lambda r: abs(float(r["avg_drop"])))
    layer_names = {1: "structural", 2: "interaction", 3: "behavioral", 4: "rule"}
    layer_name = layer_names.get(worst_layer["layer"], "unknown")
    return (
        f"Layer '{layer_name}' shows the most instability. "
        "Consider increasing exploration frequency for this layer."
    )
