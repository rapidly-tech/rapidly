"""FastAPI test client and dependency-override fixtures."""

from collections.abc import AsyncGenerator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from rapidly.app import app as rapidly_app
from rapidly.identity.auth.dependencies import (
    _factory_cache as _auth_subject_factory_cache,
)
from rapidly.identity.auth.models import AuthPrincipal, Subject
from rapidly.postgres import AsyncSession, get_db_read_session, get_db_session
from rapidly.redis import Redis, get_redis

# ── Session-aware HTTP client ──


class SessionResettingClient(httpx.AsyncClient):
    """HTTP client that expunges the ORM session before every request.

    This mirrors production behaviour where each request gets a fresh session,
    surfacing lazy-loading errors that would silently pass with a shared session.

    Opt out per-test with ``@pytest.mark.keep_session_state``.
    """

    def __init__(self, session: AsyncSession, *, reset: bool = True, **kwargs: Any):
        super().__init__(**kwargs)
        self._session = session
        self._reset = reset

    async def request(self, *args: Any, **kwargs: Any) -> httpx.Response:
        if self._reset:
            self._session.expunge_all()
        return await super().request(*args, **kwargs)


# ── Dependency override fixtures ──


@pytest_asyncio.fixture
async def app(
    auth_subject: AuthPrincipal[Subject], session: AsyncSession, redis: Redis
) -> AsyncGenerator[FastAPI]:
    rapidly_app.dependency_overrides[get_db_session] = lambda: session
    rapidly_app.dependency_overrides[get_db_read_session] = lambda: session
    rapidly_app.dependency_overrides[get_redis] = lambda: redis
    for auth_subject_getter in _auth_subject_factory_cache.values():
        rapidly_app.dependency_overrides[auth_subject_getter] = lambda: auth_subject

    yield rapidly_app

    rapidly_app.dependency_overrides.pop(get_db_session)


@pytest_asyncio.fixture
async def client(
    app: FastAPI, session: AsyncSession, request: pytest.FixtureRequest
) -> AsyncGenerator[httpx.AsyncClient, None]:
    # Check if test wants to keep session state (opt-out)
    keep_state = request.node.get_closest_marker("keep_session_state") is not None
    auto_expunge = not keep_state

    async with SessionResettingClient(
        session=session,
        reset=auto_expunge,
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
