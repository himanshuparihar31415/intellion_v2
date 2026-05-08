"""Session history and meso-loop analytics."""
import uuid
from fastapi import APIRouter, Query
from ..db import get_pool
from ..db.repositories import SessionRepository
from ..feedback.meso_loop import extract_session_patterns

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("")
async def list_sessions(intellion_id: uuid.UUID = Query(...), limit: int = Query(20, le=100)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        repo = SessionRepository(conn)
        sessions = await repo.list_for_intellion(intellion_id, limit=limit)
        return {"sessions": [s.model_dump() for s in sessions]}


@router.get("/analytics")
async def session_analytics(intellion_id: uuid.UUID = Query(...), days: int = Query(30, le=365)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await extract_session_patterns(conn, intellion_id, lookback_days=days)
