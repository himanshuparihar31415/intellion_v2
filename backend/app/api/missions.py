"""Mission execution endpoints."""
import uuid
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from ..db import get_pool
from ..reasoning.models import TestPlan
from ..working.mission import MissionResult, MissionRunner

router = APIRouter(prefix="/missions", tags=["missions"])

_mission_results: dict[str, dict] = {}


class RunMissionRequest(BaseModel):
    intellion_id: uuid.UUID
    plan: TestPlan


@router.post("")
async def run_mission(req: RunMissionRequest, background_tasks: BackgroundTasks):
    pool = await get_pool()
    async with pool.acquire() as conn:
        intellion = await conn.fetchrow(
            "SELECT * FROM intellions WHERE id = $1", req.intellion_id
        )
        if not intellion:
            raise HTTPException(404, "Intellion not found")

        session_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO sessions (id, intellion_id, session_type) VALUES ($1, $2, 'working')",
            session_id,
            req.intellion_id,
        )

    mission_id = str(uuid.uuid4())
    _mission_results[mission_id] = {"status": "running"}

    async def _run():
        p = await get_pool()
        async with p.acquire() as conn:
            runner = MissionRunner(
                conn,
                req.intellion_id,
                session_id,
                intellion["target_url"],
            )
            result = await runner.run(req.plan)
            _mission_results[mission_id] = {
                "status": "completed",
                "mission_id": str(result.mission_id),
                "steps_executed": result.steps_executed,
                "success": result.success,
                "sync_summary": result.sync_summary,
                "findings": [
                    {
                        "step": f.step_number,
                        "type": f.finding_type.value,
                        "description": f.description,
                    }
                    for f in result.findings
                ],
            }

    background_tasks.add_task(_run)
    return {"mission_id": mission_id, "session_id": str(session_id), "status": "running"}


@router.get("/{mission_id}")
async def get_mission(mission_id: str):
    result = _mission_results.get(mission_id)
    if not result:
        raise HTTPException(404, "Mission not found")
    return result
