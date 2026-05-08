"""APScheduler daily decay job wired into FastAPI lifespan."""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from ..db import get_pool
from ..feedback.decay import run_decay

_scheduler: AsyncIOScheduler | None = None


async def _decay_job() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await run_decay(conn)
        print(f"[decay] {result}")


def start_scheduler() -> None:
    global _scheduler
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(_decay_job, "cron", hour=3, minute=0, id="nightly_decay")
    _scheduler.start()


def stop_scheduler() -> None:
    if _scheduler:
        _scheduler.shutdown(wait=False)
