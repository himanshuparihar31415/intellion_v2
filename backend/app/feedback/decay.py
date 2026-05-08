"""
DecayScheduler: daily confidence decay job.
Rates (from feedback_architecture.html):
  human-taught:   0.2%/day after 30 days
  test-confirmed: 0.1%/day after 21 days
  exploration:    0.5%/day after 14 days
  document:       0.3%/day after 21 days
When confidence drops below 60, set verify_due_at = NOW() + 7 days.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import asyncpg

from ..config import settings
from ..models.enums import TriggerType


async def run_decay(conn: asyncpg.Connection) -> dict:
    """Apply passive decay to all active nodes whose decay period has elapsed."""
    now = datetime.utcnow()

    # Decay rates by source type (% per day)
    decay_config = [
        ("human", settings.decay_human_daily_rate, 30),
        ("test_execution", settings.decay_test_daily_rate, 21),
        ("exploration", settings.decay_exploration_daily_rate, 14),
        ("document", settings.decay_document_daily_rate, 21),
    ]

    total_decayed = 0
    for source_type, rate, start_days in decay_config:
        # Find nodes whose primary source is this type and decay period has started
        rows = await conn.fetch(
            """
            SELECT DISTINCT n.id, n.confidence
            FROM nodes n
            JOIN node_sources ns ON ns.node_id = n.id
            WHERE n.status = 'active'
              AND ns.source_type = $1
              AND n.last_verified_at < $2
              AND n.confidence > n.confidence_floor
            ORDER BY n.id
            """,
            source_type,
            now - timedelta(days=start_days),
        )

        if not rows:
            continue

        affected_ids = [r["id"] for r in rows]
        drop = rate  # % drop

        await conn.execute(
            """
            UPDATE nodes
            SET confidence = GREATEST(confidence_floor, confidence - $1),
                updated_at = $2
            WHERE id = ANY($3)
            """,
            drop,
            now,
            affected_ids,
        )

        # Set verify_due_at for nodes that dropped below 60
        await conn.execute(
            """
            UPDATE nodes
            SET verify_due_at = $1
            WHERE id = ANY($2) AND confidence < 60 AND (verify_due_at IS NULL OR verify_due_at < $1)
            """,
            now + timedelta(days=7),
            affected_ids,
        )

        # Log decay event
        await conn.execute(
            """
            INSERT INTO decay_events (
                trigger_type, trigger_reference, affected_node_ids,
                confidence_drop, recomputed_at, reverify_queued
            ) VALUES ($1, $2, $3, $4, $5, $6)
            """,
            TriggerType.TIME_DECAY.value,
            f"nightly_{source_type}",
            affected_ids,
            drop,
            now,
            True,
        )

        total_decayed += len(affected_ids)

    return {"nodes_decayed": total_decayed, "run_at": now.isoformat()}
