import os
from ..connection import get_pool

MIGRATION_DIR = os.path.dirname(__file__)


async def run_migration_sql(filename: str = "001_initial.sql") -> None:
    pool = await get_pool()
    path = os.path.join(MIGRATION_DIR, filename)
    with open(path) as f:
        sql = f.read()
    async with pool.acquire() as conn:
        await conn.execute(sql)
