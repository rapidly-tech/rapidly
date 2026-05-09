"""Tests for ``rapidly/postgres.py``.

Per-request DB session management. Three load-bearing surfaces:

- ``AsyncSessionMiddleware`` only opens a session for ``http`` /
  ``websocket`` scopes — bypassing for ``lifespan`` is essential
  because lifespan runs BEFORE request state is populated; opening
  a session there would crash on the missing sessionmaker
- ``get_db_session`` commits on success, rolls back on exception —
  the framework-level transaction contract every endpoint depends
  on
- ``_app_label`` produces ``{env}.{process_name}`` strings for
  Postgres ``application_name`` so ``pg_stat_activity`` rows are
  attributable to the right process (api / worker / scheduler)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from rapidly.config import settings
from rapidly.postgres import (
    _FINALISE_ERR,
    _FINALISE_OK,
    _SESSION_SCOPE_TYPES,
    AsyncSessionMiddleware,
    _app_label,
    get_db_read_session,
    get_db_session,
    get_db_sessionmaker,
)


class TestSessionScopeTypes:
    def test_only_http_and_websocket(self) -> None:
        # Lifespan + non-IO scope types must NOT trigger the session
        # middleware; lifespan runs before request state is populated
        # and would crash on the missing sessionmaker.
        assert _SESSION_SCOPE_TYPES == frozenset({"http", "websocket"})


class TestFinaliseLiterals:
    def test_commit_and_rollback_strings(self) -> None:
        # Pinning the string-based call format prevents a regression
        # to ``getattr(session, "close")`` which would skip the
        # commit AND lose pending changes.
        assert _FINALISE_OK == "commit"
        assert _FINALISE_ERR == "rollback"


class TestAppLabel:
    def test_format_is_env_dot_process(self) -> None:
        # ``pg_stat_activity.application_name`` rows the SREs read
        # to attribute connections — drift here makes dashboards
        # show ``unknown`` for the affected process.
        assert _app_label("worker") == f"{settings.ENV.value}.worker"
        assert _app_label("scheduler") == f"{settings.ENV.value}.scheduler"


@pytest.mark.asyncio
class TestAsyncSessionMiddleware:
    async def test_passes_lifespan_scope_through_untouched(self) -> None:
        downstream = AsyncMock()
        mw = AsyncSessionMiddleware(downstream)
        scope: dict[str, Any] = {"type": "lifespan", "state": {}}
        await mw(scope, AsyncMock(), AsyncMock())
        downstream.assert_awaited_once()
        # No session was set on the scope (the middleware bailed).
        assert "async_session" not in scope.get("state", {})

    async def test_opens_session_for_http_scope(self) -> None:
        # The session is created via the maker on
        # ``scope["state"]["async_sessionmaker"]`` and stashed at
        # ``scope["state"]["async_session"]`` for downstream
        # dependency resolution.
        session = MagicMock(name="session")

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=False)
        maker = MagicMock(return_value=cm)

        captured: dict[str, Any] = {}

        async def downstream(scope: Any, _r: Any, _s: Any) -> None:
            captured["session"] = scope["state"]["async_session"]

        mw = AsyncSessionMiddleware(downstream)
        scope: dict[str, Any] = {
            "type": "http",
            "state": {"async_sessionmaker": maker},
        }
        await mw(scope, AsyncMock(), AsyncMock())
        assert captured["session"] is session

    async def test_opens_session_for_websocket_scope(self) -> None:
        # Same path as HTTP — websocket handlers also get a session.
        session = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=False)
        maker = MagicMock(return_value=cm)
        downstream = AsyncMock()
        mw = AsyncSessionMiddleware(downstream)
        scope: dict[str, Any] = {
            "type": "websocket",
            "state": {"async_sessionmaker": maker},
        }
        await mw(scope, AsyncMock(), AsyncMock())
        downstream.assert_awaited_once()


@pytest.mark.asyncio
class TestGetDbSessionmaker:
    async def test_returns_request_state_sessionmaker(self) -> None:
        sentinel = MagicMock(name="maker")
        request = MagicMock()
        request.state.async_sessionmaker = sentinel
        assert await get_db_sessionmaker(request) is sentinel


@pytest.mark.asyncio
class TestGetDbSession:
    async def test_yields_request_state_session_and_commits(self) -> None:
        # Happy path: yield the stashed session, commit on success.
        session = MagicMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        request = MagicMock()
        request.state.async_session = session

        async for s in get_db_session(request):
            assert s is session

        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()

    async def test_rolls_back_on_exception(self) -> None:
        # Load-bearing transaction-integrity pin. Without rollback,
        # a partial write from a failed handler would persist.
        session = MagicMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        request = MagicMock()
        request.state.async_session = session

        gen = get_db_session(request)
        await gen.asend(None)
        with pytest.raises(RuntimeError, match="boom"):
            await gen.athrow(RuntimeError("boom"))
        session.rollback.assert_awaited_once()
        session.commit.assert_not_awaited()

    async def test_raises_runtime_error_when_session_missing(self) -> None:
        # Defensive guard: if the middleware didn't run (forgot to
        # add it, scope type bypassed), the dependency must crash
        # loudly with a diagnostic message rather than silently
        # AttributeError.
        request = MagicMock(spec=[])  # no state attribute
        request.state = MagicMock(spec=[])  # state has no attrs

        gen = get_db_session(request)
        with pytest.raises(RuntimeError, match="AsyncSessionMiddleware"):
            await gen.asend(None)


@pytest.mark.asyncio
class TestGetDbReadSession:
    async def test_opens_read_session_via_replica_maker(self) -> None:
        session = MagicMock(name="read-session")
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=False)
        maker = MagicMock(return_value=cm)
        request = MagicMock()
        request.state.async_read_sessionmaker = maker

        async for s in get_db_read_session(request):
            assert s is session
