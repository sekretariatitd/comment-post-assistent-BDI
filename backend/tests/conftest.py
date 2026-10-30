"""Test fixtures. Tests run against a throwaway `app_test` database built by the real migrations."""

import asyncio
from argparse import Namespace
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from alembic import command
from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models import User, UserRole
from app.services import auth_service
from app.workers.queue import get_queue

TEST_DB_NAME = "app_test"
BACKEND_DIR = Path(__file__).resolve().parent.parent


def _run_migrations(url: str) -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.cmd_opts = Namespace(x=[f"url={url}"])
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
async def test_engine() -> AsyncIterator[AsyncEngine]:
    base_url = make_url(get_settings().database_url)
    admin = create_async_engine(base_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    async with admin.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE)"))
        await conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
    await admin.dispose()

    test_url = base_url.set(database=TEST_DB_NAME)
    # env.py calls asyncio.run(), so run migrations off the test event loop.
    await asyncio.to_thread(_run_migrations, test_url.render_as_string(hide_password=False))

    engine = create_async_engine(test_url, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session whose changes are rolled back after each test."""
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(
            bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()


class FakeQueue:
    """Records enqueued jobs instead of sending them to Redis (and the real worker)."""

    def __init__(self) -> None:
        self.jobs: list[tuple[str, tuple[Any, ...], str]] = []

    async def enqueue_job(self, name: str, *args: Any, _job_id: str) -> object | None:
        if any(job_id == _job_id for *_, job_id in self.jobs):
            return None
        self.jobs.append((name, args, _job_id))
        return object()


@pytest.fixture
def queue() -> FakeQueue:
    return FakeQueue()


@pytest.fixture
async def client(db_session: AsyncSession, queue: FakeQueue) -> AsyncIterator[AsyncClient]:
    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_queue] = lambda: queue
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.clear()


async def _user_headers(db: AsyncSession, email: str, role: UserRole) -> dict[str, str]:
    user: User = await auth_service.create_user(db, email, "pw-123", role)
    return {"Authorization": f"Bearer {create_access_token(user.id, role.value)}"}


@pytest.fixture
async def admin_headers(db_session: AsyncSession) -> dict[str, str]:
    return await _user_headers(db_session, "admin-test@example.com", UserRole.admin)


@pytest.fixture
async def reviewer_headers(db_session: AsyncSession) -> dict[str, str]:
    return await _user_headers(db_session, "reviewer-test@example.com", UserRole.reviewer)
