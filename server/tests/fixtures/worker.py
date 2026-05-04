"""Dramatiq worker fixtures with patched middleware for isolated testing."""

from collections.abc import AsyncIterator, Iterator
from typing import Any

import dramatiq
import httpx
import pytest
import pytest_asyncio
from dramatiq.middleware.current_message import CurrentMessage
from pytest_mock import MockerFixture

from rapidly.config import settings
from rapidly.core.db.postgres import AsyncSession
from rapidly.redis import Redis
from rapidly.worker import JobQueueManager, RedisMiddleware
from rapidly.worker._enqueue import _job_queue_manager
from rapidly.worker._httpx import HTTPXMiddleware
from rapidly.worker._sqlalchemy import SQLAlchemyMiddleware

# ── Job queue fixtures ──


@pytest.fixture(autouse=True)
def set_job_queue_manager_context() -> None:
    _job_queue_manager.set(JobQueueManager())


@pytest_asyncio.fixture
async def httpx_client() -> AsyncIterator[httpx.AsyncClient]:
    client = httpx.AsyncClient()
    yield client
    await client.aclose()


# ── Middleware patches ──


@pytest.fixture(autouse=True)
def patch_middlewares(
    mocker: MockerFixture,
    session: AsyncSession,
    redis: Redis,
    httpx_client: httpx.AsyncClient,
) -> None:
    mocker.patch.object(SQLAlchemyMiddleware, "get_async_session", return_value=session)
    mocker.patch.object(RedisMiddleware, "get", return_value=redis)
    mocker.patch.object(HTTPXMiddleware, "get", return_value=httpx_client)


# ── Message context fixtures ──


@pytest.fixture(autouse=True)
def current_message() -> Iterator[dramatiq.Message[Any]]:
    message: dramatiq.Message[Any] = dramatiq.Message(
        queue_name="default",
        actor_name="actor",
        args=(),
        kwargs={},
        options={"retries": 0, "max_retries": settings.WORKER_MAX_RETRIES},
    )
    CurrentMessage._MESSAGE.set(message)
    yield message
    CurrentMessage._MESSAGE.set(None)
