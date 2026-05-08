from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import get_pool, close_pool
from .workers.decay_worker import start_scheduler, stop_scheduler
from .api.health import router as health_router
from .api.intellions import router as intellions_router
from .api.training import router as training_router
from .api.graph import router as graph_router
from .api.reasoning import router as reasoning_router
from .api.missions import router as missions_router
from .api.webhooks import router as webhooks_router
from .api.sessions import router as sessions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()
    start_scheduler()
    yield
    stop_scheduler()
    await close_pool()


app = FastAPI(title="Intellion", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(intellions_router)
app.include_router(training_router)
app.include_router(graph_router)
app.include_router(reasoning_router)
app.include_router(missions_router)
app.include_router(webhooks_router)
app.include_router(sessions_router)
