"""
Integration test fixtures. Requires a running PostgreSQL + pgvector instance.
Set DATABASE_URL env var or use docker-compose.
"""
import os
import uuid
import pytest
import asyncpg
from app.db.connection import get_pool, close_pool
from app.db.migrations import run_migration_sql


@pytest.fixture(scope="session")
def database_url():
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://intellion:intellion@localhost:5432/intellion_test",
    )


@pytest.fixture(scope="session")
async def db_pool(database_url):
    import app.config as cfg
    cfg.settings.database_url = database_url
    pool = await get_pool()
    yield pool
    await close_pool()


@pytest.fixture
async def conn(db_pool):
    async with db_pool.acquire() as connection:
        tr = connection.transaction()
        await tr.start()
        yield connection
        await tr.rollback()  # rollback after each test


@pytest.fixture
async def intellion_id(conn):
    iid = uuid.uuid4()
    await conn.execute(
        "INSERT INTO intellions (id, name, target_url) VALUES ($1, $2, $3)",
        iid,
        "Test Intellion",
        "http://localhost:3000",
    )
    return iid


@pytest.fixture
async def session_id(conn, intellion_id):
    sid = uuid.uuid4()
    await conn.execute(
        "INSERT INTO sessions (id, intellion_id, session_type) VALUES ($1, $2, $3)",
        sid,
        intellion_id,
        "training",
    )
    return sid
