"""Graph browsing endpoints: nodes, edges, conflicts."""
import uuid
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from ..db import get_pool
from ..db.repositories import NodeRepository, EdgeRepository, ConflictRepository
from ..models.enums import ConflictResolution, Layer
from ..models.graph import Node, Edge, Conflict

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/nodes")
async def list_nodes(
    intellion_id: uuid.UUID = Query(...),
    layer: int | None = Query(None),
    page: int = Query(0, ge=0),
    page_size: int = Query(50, le=200),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        repo = NodeRepository(conn)
        nodes = await repo.list_active(
            intellion_id,
            layer=Layer(layer) if layer else None,
            page=page,
            page_size=page_size,
        )
        return {"nodes": [n.model_dump(exclude={"semantic_embedding"}) for n in nodes], "page": page}


@router.get("/nodes/{node_id}")
async def get_node(node_id: uuid.UUID):
    pool = await get_pool()
    async with pool.acquire() as conn:
        repo = NodeRepository(conn)
        node = await repo.get(node_id)
        if not node:
            raise HTTPException(404, "Node not found")
        sources = await repo.get_sources(node_id)
        edge_repo = EdgeRepository(conn)
        edges = await edge_repo.get_outbound(node_id)
        return {
            "node": node.model_dump(exclude={"semantic_embedding"}),
            "sources": [s.model_dump() for s in sources],
            "edges": [e.model_dump() for e in edges],
        }


@router.get("/conflicts")
async def list_conflicts(intellion_id: uuid.UUID = Query(...)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        repo = ConflictRepository(conn)
        conflicts = await repo.list_unresolved(intellion_id)
        return {"conflicts": [c.model_dump() for c in conflicts]}


class ResolveConflictRequest(BaseModel):
    resolution: str
    resolved_by: uuid.UUID | None = None


@router.patch("/conflicts/{conflict_id}")
async def resolve_conflict(conflict_id: uuid.UUID, req: ResolveConflictRequest):
    pool = await get_pool()
    async with pool.acquire() as conn:
        repo = ConflictRepository(conn)
        try:
            resolution = ConflictResolution(req.resolution)
        except ValueError:
            raise HTTPException(400, f"Invalid resolution: {req.resolution}")
        await repo.resolve(conflict_id, resolution, req.resolved_by)
        return {"status": "resolved"}


@router.get("/nodes/{node_id}/impact")
async def impact_analysis(node_id: uuid.UUID, max_depth: int = Query(5, le=8)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        repo = EdgeRepository(conn)
        results = await repo.impact_analysis(node_id, max_depth)
        return {"impacted_nodes": results}
