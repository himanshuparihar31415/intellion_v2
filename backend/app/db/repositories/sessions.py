from __future__ import annotations
import uuid
from datetime import datetime
import asyncpg
from ...models.graph import Session


class SessionRepository:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    async def insert(self, session: Session) -> Session:
        await self._conn.execute(
            """
            INSERT INTO sessions (id, intellion_id, session_type, status, coverage_score, created_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            session.id,
            session.intellion_id,
            session.session_type,
            session.status,
            session.coverage_score,
            session.created_at,
        )
        return session

    async def get(self, session_id: uuid.UUID) -> Session | None:
        row = await self._conn.fetchrow("SELECT * FROM sessions WHERE id = $1", session_id)
        return Session(**dict(row)) if row else None

    async def complete(
        self, session_id: uuid.UUID, coverage_score: float | None = None
    ) -> None:
        await self._conn.execute(
            """
            UPDATE sessions
            SET status = 'completed', completed_at = $2, coverage_score = COALESCE($3, coverage_score)
            WHERE id = $1
            """,
            session_id,
            datetime.utcnow(),
            coverage_score,
        )

    async def fail(self, session_id: uuid.UUID) -> None:
        await self._conn.execute(
            "UPDATE sessions SET status = 'failed', completed_at = $2 WHERE id = $1",
            session_id,
            datetime.utcnow(),
        )

    async def list_for_intellion(
        self, intellion_id: uuid.UUID, limit: int = 20
    ) -> list[Session]:
        rows = await self._conn.fetch(
            "SELECT * FROM sessions WHERE intellion_id = $1 ORDER BY created_at DESC LIMIT $2",
            intellion_id,
            limit,
        )
        return [Session(**dict(r)) for r in rows]
