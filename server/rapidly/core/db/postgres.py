"""Async and sync PostgreSQL engine/session factories.

Typed session aliases enforce read vs. read-write intent at the
type-checker level:

    AsyncReadSession  -- query-only paths
    AsyncSession      -- mutation paths (superset of read)
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, NewType

from sqlalchemy import Engine
from sqlalchemy import create_engine as _sa_create_sync_engine
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession as _RawAsyncSession
from sqlalchemy.ext.asyncio import (
    create_async_engine as _sa_create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from ..extensions.sqlalchemy import sql

# ---------------------------------------------------------------------------
# Session type aliases
# ---------------------------------------------------------------------------

AsyncReadSession = NewType("AsyncReadSession", _RawAsyncSession)
"""Type-level marker for read-only database sessions."""

AsyncSession = NewType("AsyncSession", AsyncReadSession)
"""Type-level marker for read-write database sessions."""


# ---------------------------------------------------------------------------
# JSON serialisation for JSONB columns
# ---------------------------------------------------------------------------


def _decimal_aware_default(value: Any) -> Any:
    """Convert ``Decimal`` to ``float`` for JSON encoding."""
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Cannot JSON-encode {type(value).__name__}")


def json_serializer(payload: Any) -> str:
    """JSON encoder passed to SQLAlchemy engines for JSONB round-tripping."""
    return json.dumps(payload, default=_decimal_aware_default)


# ---------------------------------------------------------------------------
# Engine factories
# ---------------------------------------------------------------------------


def _async_connect_args(
    application_name: str | None,
    command_timeout: float | None,
) -> dict[str, Any]:
    """Build ``connect_args`` for asyncpg."""
    out: dict[str, Any] = {}
    if application_name is not None:
        out["server_settings"] = {"application_name": application_name}
    if command_timeout is not None:
        out["command_timeout"] = command_timeout
    return out


def _sync_connect_args(
    application_name: str | None,
    command_timeout: float | None,
) -> dict[str, Any]:
    """Build ``connect_args`` for psycopg2."""
    out: dict[str, Any] = {}
    if application_name is not None:
        out["application_name"] = application_name
    if command_timeout is not None:
        out["options"] = f"-c statement_timeout={int(command_timeout * 1000)}"
    return out


def create_async_engine(
    *,
    dsn: str,
    application_name: str | None = None,
    pool_logging_name: str | None = None,
    pool_size: int | None = None,
    pool_recycle: int | None = None,
    command_timeout: float | None = None,
    debug: bool = False,
) -> AsyncEngine:
    return _sa_create_async_engine(
        dsn,
        echo=debug,
        connect_args=_async_connect_args(application_name, command_timeout),
        pool_size=pool_size,
        pool_recycle=pool_recycle,
        pool_logging_name=pool_logging_name,
        json_serializer=json_serializer,
    )


def create_sync_engine(
    *,
    dsn: str,
    application_name: str | None = None,
    pool_logging_name: str | None = None,
    pool_size: int | None = None,
    pool_recycle: int | None = None,
    command_timeout: float | None = None,
    debug: bool = False,
) -> Engine:
    return _sa_create_sync_engine(
        dsn,
        echo=debug,
        connect_args=_sync_connect_args(application_name, command_timeout),
        pool_size=pool_size,
        pool_recycle=pool_recycle,
        pool_logging_name=pool_logging_name,
    )


# ---------------------------------------------------------------------------
# Session-maker helpers
# ---------------------------------------------------------------------------

type AsyncSessionMaker = async_sessionmaker[AsyncSession]
type AsyncReadSessionMaker = async_sessionmaker[AsyncReadSession]


def create_async_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=_RawAsyncSession)  # type: ignore[return-value]


type SyncSessionMaker = sessionmaker[Session]


def create_sync_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "AsyncEngine",
    "AsyncReadSession",
    "AsyncReadSessionMaker",
    "AsyncSession",
    "AsyncSessionMaker",
    "Engine",
    "Session",
    "SyncSessionMaker",
    "create_async_engine",
    "create_async_sessionmaker",
    "create_sync_engine",
    "create_sync_sessionmaker",
    "sql",
]
