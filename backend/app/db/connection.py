from __future__ import annotations
import asyncpg
from ..config import settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def run_migration(sql_path: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        with open(sql_path) as f:
            await conn.execute(f.read())
