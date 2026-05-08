"""Training channel endpoints."""
import asyncio
import uuid
from typing import Annotated
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from ..db import get_pool
from ..models.enums import Layer
from ..models.graph import Session
from ..training.channels.human import HumanTeachingChannel
from ..training.channels.document import DocumentIngestionChannel
from ..training.channels.schema import SchemaIngestionChannel
from ..training.explorer.agent import ExplorationAgent

router = APIRouter(prefix="/training", tags=["training"])

# In-memory status store (production would use Redis or DB)
_exploration_status: dict[str, dict] = {}


class TeachRequest(BaseModel):
    intellion_id: uuid.UUID
    semantic_id: str
    fact: str
    layer: int
    page_path: str | None = None


@router.post("/teach")
async def teach(req: TeachRequest):
    pool = await get_pool()
    async with pool.acquire() as conn:
        session_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO sessions (id, intellion_id, session_type) VALUES ($1, $2, 'training')",
            session_id, req.intellion_id,
        )
        ch = HumanTeachingChannel(conn, req.intellion_id, session_id)
        result = await ch.run(
            semantic_id=req.semantic_id,
            fact=req.fact,
            layer=Layer(req.layer),
            page_path=req.page_path,
        )
        await conn.execute(
            "UPDATE sessions SET status = 'completed', completed_at = now() WHERE id = $1",
            session_id,
        )
        return result


@router.post("/ingest/document")
async def ingest_document(
    intellion_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
):
    content = await file.read()
    doc_type = "pdf" if file.filename and file.filename.endswith(".pdf") else "text"
    pool = await get_pool()
    async with pool.acquire() as conn:
        session_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO sessions (id, intellion_id, session_type) VALUES ($1, $2, 'training')",
            session_id, intellion_id,
        )
        ch = DocumentIngestionChannel(conn, intellion_id, session_id)
        result = await ch.run(content=content, filename=file.filename or "upload", doc_type=doc_type)
        await conn.execute(
            "UPDATE sessions SET status = 'completed', completed_at = now() WHERE id = $1",
            session_id,
        )
        return result


class SchemaIngestRequest(BaseModel):
    intellion_id: uuid.UUID
    content: str
    schema_type: str  # openapi | graphql | sql


@router.post("/ingest/schema")
async def ingest_schema(req: SchemaIngestRequest):
    pool = await get_pool()
    async with pool.acquire() as conn:
        session_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO sessions (id, intellion_id, session_type) VALUES ($1, $2, 'training')",
            session_id, req.intellion_id,
        )
        ch = SchemaIngestionChannel(conn, req.intellion_id, session_id)
        result = await ch.run(content=req.content, schema_type=req.schema_type)
        await conn.execute(
            "UPDATE sessions SET status = 'completed', completed_at = now() WHERE id = $1",
            session_id,
        )
        return result


class ExploreRequest(BaseModel):
    intellion_id: uuid.UUID


@router.post("/explore/start")
async def start_exploration(req: ExploreRequest, background_tasks: BackgroundTasks):
    pool = await get_pool()
    async with pool.acquire() as conn:
        intellion = await conn.fetchrow("SELECT * FROM intellions WHERE id = $1", req.intellion_id)
        if not intellion:
            raise HTTPException(404, "Intellion not found")

        session_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO sessions (id, intellion_id, session_type) VALUES ($1, $2, 'training')",
            session_id, req.intellion_id,
        )

    _exploration_status[str(session_id)] = {"status": "running", "steps_taken": 0, "nodes_written": 0}

    async def _run():
        p = await get_pool()
        async with p.acquire() as conn:
            agent = ExplorationAgent(conn, req.intellion_id, session_id, intellion["target_url"])
            status = await agent.run()
            _exploration_status[str(session_id)] = {
                "status": "completed",
                "steps_taken": status.steps_taken,
                "nodes_written": status.nodes_written,
                "coverage_score": status.coverage_score,
            }

    background_tasks.add_task(_run)
    return {"session_id": str(session_id), "status": "running"}


@router.get("/explore/{session_id}/status")
async def exploration_status(session_id: uuid.UUID):
    status = _exploration_status.get(str(session_id))
    if not status:
        raise HTTPException(404, "Session not found")
    return status
