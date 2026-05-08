"""Reasoning engine endpoint: NL task → TestPlan."""
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..db import get_pool
from ..reasoning.engine import ReasoningEngine
from ..reasoning.models import ReasoningResult

router = APIRouter(prefix="/reason", tags=["reasoning"])


class ReasonRequest(BaseModel):
    intellion_id: uuid.UUID
    task: str


@router.post("", response_model=ReasoningResult)
async def reason(req: ReasonRequest):
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Create a working session for this reasoning run
        session_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO sessions (id, intellion_id, session_type) VALUES ($1, $2, 'working')",
            session_id,
            req.intellion_id,
        )
        engine = ReasoningEngine(conn, session_id)
        result = await engine.reason(req.intellion_id, req.task)
        await conn.execute(
            "UPDATE sessions SET status = 'completed', completed_at = now() WHERE id = $1",
            session_id,
        )
        return result
