"""Tests for ``rapidly/worker/_redis.py``.

Dramatiq lifecycle middleware for a shared Redis connection. Mirrors
the structure of ``_httpx.py`` (Phase 154): one connection per
worker process pooled across actors.

Pins:
- ``RedisMiddleware.get()`` raises ``RuntimeError`` when ``_conn`` is
  None (loud-crash-now beats silent-None-later)
- ``before_worker_boot`` calls ``create_redis("worker")`` so the
  Redis ``CLIENT LIST`` output attributes connections to the worker
  process (ops + diagnostics)
- ``_teardown_redis`` closes with ``True`` (closes the underlying
  connection pool, not just the client wrapper) and resets state
- Noop teardown when ``_conn`` is None (shutdown-before-boot safe)
- ``_REDIS_APP_NAME = "worker"`` literal pin — silent rename would
  desync the `CLIENT LIST` operator-readable name
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from rapidly.worker import _redis as M
from rapidly.worker._redis import _REDIS_APP_NAME, RedisMiddleware, _teardown_redis


@pytest.fixture(autouse=True)
def reset_conn() -> object:
    """Reset module-level ``_conn`` around every test."""
    original = M._conn
    M._conn = None
    try:
        yield
    finally:
        M._conn = original


class TestConstants:
    def test_app_name_is_worker(self) -> None:
        # Pinning the literal — appears on Redis ``CLIENT LIST``
        # output as ``{env}.worker``; ops use this to attribute
        # connections to the right process.
        assert _REDIS_APP_NAME == "worker"


class TestGetWithoutInit:
    def test_raises_runtime_error_when_conn_is_none(self) -> None:
        # Same defensive pin as the httpx middleware: an actor
        # firing before ``before_worker_boot`` ran must crash
        # loudly rather than silently get None.
        M._conn = None
        with pytest.raises(RuntimeError, match="not been initialised"):
            RedisMiddleware.get()


class TestGetAfterInit:
    def test_returns_module_level_conn(self) -> None:
        sentinel = MagicMock(name="redis-conn")
        M._conn = sentinel
        assert RedisMiddleware.get() is sentinel


class TestBeforeWorkerBoot:
    def test_calls_create_redis_with_worker_app_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        def fake_create_redis(app_name: object) -> MagicMock:
            captured["app_name"] = app_name
            return MagicMock(name="redis-client")

        monkeypatch.setattr("rapidly.worker._redis.create_redis", fake_create_redis)
        mw = RedisMiddleware()
        mw.before_worker_boot(MagicMock(), MagicMock())
        assert captured["app_name"] == _REDIS_APP_NAME
        assert M._conn is not None

    def test_replaces_existing_conn_on_reboot(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Re-boot must build a fresh connection; reusing a closed
        # one would surface as connection-pool exhaustion errors
        # on the next actor.
        monkeypatch.setattr(
            "rapidly.worker._redis.create_redis",
            lambda _: MagicMock(name="new-redis"),
        )
        first = MagicMock(name="old-redis")
        M._conn = first
        mw = RedisMiddleware()
        mw.before_worker_boot(MagicMock(), MagicMock())
        assert M._conn is not first


@pytest.mark.asyncio
class TestTeardownRedis:
    async def test_closes_with_true_and_resets_conn(self) -> None:
        # ``close(True)`` closes the underlying connection pool
        # (the bool arg is documented as "close_connection_pool").
        # A regression to ``close()`` would leave the pool open
        # and leak connections across worker restarts.
        fake = MagicMock(name="redis-conn")
        fake.close = AsyncMock()
        M._conn = fake
        await _teardown_redis()
        fake.close.assert_awaited_once_with(True)
        assert M._conn is None

    async def test_noop_when_conn_is_none(self) -> None:
        M._conn = None
        await _teardown_redis()
        assert M._conn is None
