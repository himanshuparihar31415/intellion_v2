"""
External event handlers: frontend deploy, API schema change.
Each marks affected nodes with verify_due_at = NOW() so they're
picked up by the exploration agent on next run.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import asyncpg

from ..models.enums import TriggerType


async def handle_frontend_deploy(
    conn: asyncpg.Connection,
    intellion_id: uuid.UUID,
    deploy_reference: str,
) -> dict:
    """Mark all structural and interaction nodes for re-verification."""
    now = datetime.utcnow()
    rows = await conn.fetch(
        """
        UPDATE nodes
        SET verify_due_at = $1, updated_at = $1
        WHERE intellion_id = $2
          AND status = 'active'
          AND layer IN (1, 2)
        RETURNING id
        """,
        now,
        intellion_id,
    )
    affected_ids = [r["id"] for r in rows]

    await _log_decay_event(conn, TriggerType.FRONTEND_DEPLOY, deploy_reference, affected_ids, 0.0, now)
    return {"affected_nodes": len(affected_ids), "trigger": "frontend_deploy"}


async def handle_schema_change(
    conn: asyncpg.Connection,
    intellion_id: uuid.UUID,
    change_reference: str,
) -> dict:
    """Mark all behavioral nodes for re-verification."""
    now = datetime.utcnow()
    rows = await conn.fetch(
        """
        UPDATE nodes
        SET verify_due_at = $1, updated_at = $1
        WHERE intellion_id = $2
          AND status = 'active'
          AND layer = 3
        RETURNING id
        """,
        now,
        intellion_id,
    )
    affected_ids = [r["id"] for r in rows]

    await _log_decay_event(conn, TriggerType.API_SCHEMA_CHANGE, change_reference, affected_ids, 0.0, now)
    return {"affected_nodes": len(affected_ids), "trigger": "api_schema_change"}


async def _log_decay_event(
    conn: asyncpg.Connection,
    trigger_type: TriggerType,
    reference: str,
    node_ids: list[uuid.UUID],
    confidence_drop: float,
    now: datetime,
) -> None:
    await conn.execute(
        """
        INSERT INTO decay_events (
            trigger_type, trigger_reference, affected_node_ids,
            confidence_drop, recomputed_at, reverify_queued
        ) VALUES ($1, $2, $3, $4, $5, $6)
        """,
        trigger_type.value,
        reference,
        node_ids,
        confidence_drop,
        now,
        True,
    )
