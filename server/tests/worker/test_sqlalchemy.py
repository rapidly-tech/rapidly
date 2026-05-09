"""Tests for ``rapidly/worker/_sqlalchemy.py``.

SQLAlchemy engine lifecycle for Dramatiq workers. Three load-bearing
pins:

- ``_resolve_pool_name`` derives a pool name from the ``--queues``
  CLI argument so that, on a worker that subscribes to a single
  queue, the SQLAlchemy logs + Postgres ``application_name`` carry
  ``worker-<queue>`` instead of the generic ``worker``. This makes
  ``pg_stat_activity`` actionable for ops.
- ``SQLAlchemyMiddleware.get_async_session`` raises ``RuntimeError``
  when the sessionmaker is None (matches the httpx / redis
  middleware's loud-crash-now-over-silent-None policy).
- ``AsyncSessionMaker`` context manager commits on success and
  rolls back on exception — the per-task transaction contract that
  every worker actor depends on.
"""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

from rapidly.worker import _sqlalchemy as M
from rapidly.worker._sqlalchemy import (
    _DEFAULT_POOL_NAME,
    AsyncSessionMaker,
    SQLAlchemyMiddleware,
    _dispose_engine,
    _resolve_pool_name,
)


@pytest.fixture(autouse=True)
def reset_module_state() -> object:
    """Save/restore the engine + sessionmaker around every test."""
    original_engine = M._engine
    original_sessionmaker = M._sessionmaker
    M._engine = None
    M._sessionmaker = None
    try:
        yield
    finally:
        M._engine = original_engine
        M._sessionmaker = original_sessionmaker


class TestDefaultPoolName:
    def test_pinned_to_worker(self) -> None:
        # ``worker`` is the fallback that ends up in
        # ``pg_stat_activity.application_name`` on a generic
        # multi-queue worker. Drift would desync ops dashboards.
        assert _DEFAULT_POOL_NAME == "worker"


class TestResolvePoolName:
    def test_no_queues_arg_returns_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["dramatiq", "rapidly.workers"])
        assert _resolve_pool_name() == "worker"

    def test_single_queue_yields_worker_dash_queue(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["dramatiq", "--queues", "high_priority"])
        assert _resolve_pool_name() == "worker-high_priority"

    def test_multiple_queues_sorted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Sorted join means two workers spawned with ``--queues=a,b``
        # and ``--queues=b,a`` produce the same pool name and share
        # the same Postgres pool slot in dashboards.
        monkeypatch.setattr(sys, "argv", ["dramatiq", "--queues", "zeta,alpha,mu"])
        assert _resolve_pool_name() == "worker-alpha-mu-zeta"

    def test_queues_flag_at_end_no_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Defensive: ``--queues`` without a following value (CLI
        # malformation) must not crash the worker boot — just fall
        # back to the default name.
        monkeypatch.setattr(sys, "argv", ["dramatiq", "--queues"])
        assert _resolve_pool_name() == "worker"


class TestGetAsyncSessionGuard:
    def test_raises_runtime_error_when_uninitialised(self) -> None:
        # Same defensive pin as the other worker middlewares: an
        # actor firing before ``before_worker_boot`` ran must crash
        # loudly rather than silently get None.
        M._sessionmaker = None
        with pytest.raises(RuntimeError, match="not initialised"):
            SQLAlchemyMiddleware.get_async_session()

    def test_returns_sessionmaker_call_result(self) -> None:
        # Once the sessionmaker is set, ``get_async_session`` calls
        # it and returns the resulting context manager — which
        # workers then ``async with`` to get a real session.
        cm = MagicMock(name="async-session-cm")
        sessionmaker = MagicMock(return_value=cm)
        M._sessionmaker = sessionmaker
        assert SQLAlchemyMiddleware.get_async_session() is cm
        sessionmaker.assert_called_once()


@pytest.mark.asyncio
class TestDisposeEngine:
    async def test_disposes_and_resets_engine(self) -> None:
        engine = MagicMock(name="engine")
        engine.dispose = AsyncMock()
        M._engine = engine
        await _dispose_engine()
        engine.dispose.assert_awaited_once()
        assert M._engine is None

    async def test_noop_when_engine_is_none(self) -> None:
        M._engine = None
        await _dispose_engine()
        assert M._engine is None


@pytest.mark.asyncio
class TestAsyncSessionMakerTransactions:
    async def test_commits_on_successful_block(self) -> None:
        # The worker per-task contract: success → commit.
        session = MagicMock(name="session")
        session.commit = AsyncMock()
        session.rollback = AsyncMock()

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=False)

        M._sessionmaker = MagicMock(return_value=cm)

        async with AsyncSessionMaker() as s:
            assert s is session

        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()

    async def test_rolls_back_on_exception(self) -> None:
        # The worker per-task contract: exception → rollback +
        # re-raise. A regression that committed on exception would
        # leak partial writes from failed actors.
        session = MagicMock(name="session")
        session.commit = AsyncMock()
        session.rollback = AsyncMock()

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=False)

        M._sessionmaker = MagicMock(return_value=cm)

        with pytest.raises(RuntimeError, match="boom"):
            async with AsyncSessionMaker():
                raise RuntimeError("boom")

        session.rollback.assert_awaited_once()
        session.commit.assert_not_awaited()
