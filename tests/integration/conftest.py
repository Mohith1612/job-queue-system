import os

import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis
from httpx import ASGITransport, AsyncClient
from slowapi import Limiter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db, get_redis
from app.db.base import Base
from app.main import create_app

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://jobqueue:jobqueue@localhost/jobqueue_test",
)


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
        try:
            await session.execute(text("DELETE FROM job_logs"))
            await session.execute(text("DELETE FROM jobs"))
            await session.commit()
        except Exception:
            await session.rollback()


@pytest.fixture
def fake_redis():
    return FakeAsyncRedis(decode_responses=True)


@pytest.fixture(autouse=True)
def patch_redis(fake_redis, monkeypatch):
    monkeypatch.setattr("app.queue.client.get_redis_pool", lambda: fake_redis)
    monkeypatch.setattr("app.services.idempotency.get_redis_pool", lambda: fake_redis)
    monkeypatch.setattr("app.services.job_service.get_redis_pool", lambda: fake_redis)


@pytest_asyncio.fixture
async def client(db_session, fake_redis):
    application = create_app()

    # Permissive rate limiter for tests
    application.state.limiter = Limiter(key_func=lambda r: "test", default_limits=["10000/minute"])

    async def override_get_db():
        yield db_session

    async def override_get_redis():
        return fake_redis

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_redis] = override_get_redis

    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
        yield ac

    application.dependency_overrides.clear()
