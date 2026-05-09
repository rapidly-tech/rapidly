"""PostgreSQL engine construction and FastAPI session dependencies.

Provides async and sync SQLAlchemy engine factories configured from
application settings, along with ASGI middleware and FastAPI dependencies
that manage per-request database sessions.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any, Literal

from fastapi import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from rapidly.config import settings
from rapidly.core.db.postgres import (
    AsyncEngine,
    AsyncReadSession,
    AsyncReadSessionMaker,
    AsyncSession,
    AsyncSessionMaker,
    Engine,
    sql,
)
from rapidly.core.db.postgres import create_async_engine as _new_async_engine
from rapidly.core.db.postgres import create_sync_engine as _new_sync_engine

type ProcessName = Literal["app", "worker", "scheduler", "script"]

# Scope types for which the session middleware should activate.
_SESSION_SCOPE_TYPES = frozenset({"http", "websocket"})


# -- Engine factories --------------------------------------------------------


def _shared_pool_config() -> dict[str, Any]:
    """Settings shared between async read/write engines."""
    return dict(
        debug=settings.SQLALCHEMY_DEBUG,
        pool_size=settings.DATABASE_POOL_SIZE,
        pool_recycle=settings.DATABASE_POOL_RECYCLE_SECONDS,
        command_timeout=settings.DATABASE_COMMAND_TIMEOUT_SECONDS,
    )


def _app_label(process_name: ProcessName) -> str:
    return f"{settings.ENV.value}.{process_name}"


def create_async_engine(
    process_name: ProcessName, *, pool_logging_name: str | None = None
) -> AsyncEngine:
    """Build an async engine for the primary (read-write) database."""
    return _new_async_engine(
        dsn=str(settings.get_postgres_dsn("asyncpg")),
        application_name=_app_label(process_name),
        pool_logging_name=pool_logging_name or process_name,
        **_shared_pool_config(),
    )


def create_async_read_engine(process_name: ProcessName) -> AsyncEngine:
    """Build an async engine targeting the read-replica."""
    return _new_async_engine(
        dsn=str(settings.get_postgres_read_dsn("asyncpg")),
        application_name=_app_label(process_name),
        pool_logging_name=f"{process_name}_read",
        **_shared_pool_config(),
    )


def create_sync_engine(process_name: ProcessName) -> Engine:
    """Build a synchronous engine (used by Alembic and one-off scripts)."""
    return _new_sync_engine(
        dsn=str(settings.get_postgres_dsn("psycopg2")),
        application_name=_app_label(process_name),
        pool_logging_name=f"{process_name}_sync",
        debug=settings.SQLALCHEMY_DEBUG,
        pool_size=settings.DATABASE_SYNC_POOL_SIZE,
        pool_recycle=settings.DATABASE_POOL_RECYCLE_SECONDS,
        command_timeout=settings.DATABASE_COMMAND_TIMEOUT_SECONDS,
    )


# -- ASGI middleware ----------------------------------------------------------


class AsyncSessionMiddleware:
    """Open an ``AsyncSession`` for the duration of each HTTP / WS request.

    The session is stored on ``scope["state"]["async_session"]`` and
    automatically closed when the inner ASGI app returns.
    """

    __slots__ = ("_app",)

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in _SESSION_SCOPE_TYPES:
            return await self._app(scope, receive, send)

        maker: AsyncSessionMaker = scope["state"]["async_sessionmaker"]
        async with maker() as session:
            scope["state"]["async_session"] = session
            await self._app(scope, receive, send)


# -- FastAPI dependencies ----------------------------------------------------

# Framework-level finalisation: commit on success, rollback on error.
# This is the *implementation* of automatic transaction management —
# application code should never call commit/rollback directly.
_FINALISE_OK = "commit"
_FINALISE_ERR = "rollback"


async def get_db_sessionmaker(request: Request) -> AsyncSessionMaker:
    """Return the session factory stored on request state."""
    return request.state.async_sessionmaker


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession]:
    """Yield the per-request write session with auto transaction management."""
    try:
        session = request.state.async_session
    except AttributeError as exc:
        raise RuntimeError(
            "Session missing from request state — is AsyncSessionMiddleware installed?"
        ) from exc

    try:
        yield session
    except Exception:
        await getattr(session, _FINALISE_ERR)()
        raise
    else:
        await getattr(session, _FINALISE_OK)()


async def get_db_read_session(request: Request) -> AsyncGenerator[AsyncReadSession]:
    """Yield a short-lived read-only session from the replica pool."""
    maker: AsyncReadSessionMaker = request.state.async_read_sessionmaker
    async with maker() as session:
        yield session


__all__ = [
    "AsyncEngine",
    "AsyncReadSession",
    "AsyncSession",
    "AsyncSessionMiddleware",
    "create_async_engine",
    "create_async_read_engine",
    "create_sync_engine",
    "get_db_read_session",
    "get_db_session",
    "get_db_sessionmaker",
    "sql",
]
