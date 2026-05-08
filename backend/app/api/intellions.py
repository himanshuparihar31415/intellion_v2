"""CRUD for Intellion instances."""
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..db import get_pool
from ..models.graph import Intellion

router = APIRouter(prefix="/intellions", tags=["intellions"])


class CreateIntellionRequest(BaseModel):
    name: str
    target_url: str


@router.post("", response_model=Intellion)
async def create_intellion(req: CreateIntellionRequest):
    pool = await get_pool()
    async with pool.acquire() as conn:
        iid = uuid.uuid4()
        await conn.execute(
            "INSERT INTO intellions (id, name, target_url) VALUES ($1, $2, $3)",
            iid, req.name, req.target_url,
        )
        row = await conn.fetchrow("SELECT * FROM intellions WHERE id = $1", iid)
        return Intellion(**dict(row))


@router.get("/{intellion_id}", response_model=Intellion)
async def get_intellion(intellion_id: uuid.UUID):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM intellions WHERE id = $1", intellion_id)
        if not row:
            raise HTTPException(404, "Intellion not found")
        return Intellion(**dict(row))
