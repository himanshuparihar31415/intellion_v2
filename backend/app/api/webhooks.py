"""External event webhooks: deploy, schema change."""
import uuid
from fastapi import APIRouter
from pydantic import BaseModel
from ..db import get_pool
from ..feedback.events import handle_frontend_deploy, handle_schema_change

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class DeployEvent(BaseModel):
    intellion_id: uuid.UUID
    deploy_reference: str = "unknown"


class SchemaChangeEvent(BaseModel):
    intellion_id: uuid.UUID
    change_reference: str = "unknown"


@router.post("/deploy")
async def on_deploy(event: DeployEvent):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await handle_frontend_deploy(conn, event.intellion_id, event.deploy_reference)


@router.post("/schema-change")
async def on_schema_change(event: SchemaChangeEvent):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await handle_schema_change(conn, event.intellion_id, event.change_reference)
