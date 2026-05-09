"""Tests for ``rapidly/redis.py``.

Connection management for the process-local Redis client. Each
process (API server, worker, rate-limiter, script) creates its own
pool via ``create_redis``; ``get_redis`` is the FastAPI dependency
that pulls the per-request instance off ``request.state``.

Load-bearing pins:
- **Retry-on-transient-error** is wired: redis-py's retry policy
  must be set at client construction so a reconnect on a dropped
  connection happens automatically. A regression dropping the
  retry would surface as request failures on every Redis
  flap (rate-limit unavailable, OAuth state lost, etc.)
- Retryable errors cover both ``ConnectionError`` AND ``TimeoutError``
- ``decode_responses=True`` keeps returned strings as ``str`` — a
  regression to bytes would break every consumer doing
  ``.get(...).decode()`` or string compares
- ``client_name`` uses the ``env.process_name`` format — ops read
  this on the Redis ``CLIENT LIST`` output to attribute connections
- ``get_redis`` pulls from ``request.state.redis``
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from redis import ConnectionError as RedisConnectionError
from redis import TimeoutError as RedisTimeoutError
from redis.asyncio.retry import Retry

from rapidly import redis as R
from rapidly.redis import (
    _RETRY_LIMIT,
    _RETRYABLE_ERRORS,
    _build_retry_policy,
    create_redis,
    get_redis,
)


class TestRetryPolicy:
    def test_retry_limit_is_50(self) -> None:
        # Pin the documented retry count; drift would change
        # how long a stuck connection stalls a request before
        # surfacing.
        assert _RETRY_LIMIT == 50

    def test_build_retry_returns_retry_instance(self) -> None:
        policy = _build_retry_policy()
        assert isinstance(policy, Retry)

    def test_retryable_errors_include_connection_and_timeout(self) -> None:
        # Both classes must be in the tuple — a regression dropping
        # TimeoutError would leave requests stalled indefinitely on
        # Redis hangs.
        assert RedisConnectionError in _RETRYABLE_ERRORS
        assert RedisTimeoutError in _RETRYABLE_ERRORS


class TestCreateRedis:
    def _captured_kwargs(self) -> tuple[MagicMock, dict[str, Any]]:
        captured: dict[str, Any] = {}

        def fake_from_url(url: str, **kwargs: Any) -> MagicMock:
            captured["url"] = url
            captured.update(kwargs)
            return MagicMock(name="Redis")

        mock_cls = MagicMock()
        mock_cls.from_url = MagicMock(side_effect=fake_from_url)
        return mock_cls, captured

    def test_decode_responses_is_true(self) -> None:
        # Load-bearing pin. Returned strings as ``str`` (not bytes)
        # keeps every consumer doing ``.get(...).lower()`` /
        # ``json.loads(...)`` working.
        mock_cls, captured = self._captured_kwargs()
        with patch("rapidly.redis._redis_async.Redis", mock_cls):
            create_redis("app")
        assert captured["decode_responses"] is True

    def test_retry_policy_is_wired(self) -> None:
        # A regression that omitted ``retry=`` would disable the
        # automatic reconnect on transient errors — every request
        # would fail on the first Redis flap.
        mock_cls, captured = self._captured_kwargs()
        with patch("rapidly.redis._redis_async.Redis", mock_cls):
            create_redis("app")
        assert isinstance(captured["retry"], Retry)

    def test_retry_on_error_lists_retryable_exceptions(self) -> None:
        mock_cls, captured = self._captured_kwargs()
        with patch("rapidly.redis._redis_async.Redis", mock_cls):
            create_redis("app")
        assert set(captured["retry_on_error"]) == set(_RETRYABLE_ERRORS)

    def test_client_name_has_env_and_process_name(self) -> None:
        # ``env.process_name`` — ops read this on ``CLIENT LIST`` to
        # attribute connections to the right process.
        mock_cls, captured = self._captured_kwargs()
        with patch("rapidly.redis._redis_async.Redis", mock_cls):
            create_redis("worker")
        # Format: ``{env}.worker``
        assert captured["client_name"].endswith(".worker")

    @pytest.mark.parametrize("process_name", ["app", "rate-limit", "worker", "script"])
    def test_accepts_documented_process_names(self, process_name: str) -> None:
        # The Literal type guards against drift. Runtime construction
        # must succeed for each.
        mock_cls, _ = self._captured_kwargs()
        with patch("rapidly.redis._redis_async.Redis", mock_cls):
            create_redis(process_name)  # type: ignore[arg-type]


@pytest.mark.asyncio
class TestGetRedis:
    async def test_returns_request_state_redis(self) -> None:
        # Lifespan stores the Redis client on request.state.redis;
        # the dependency just forwards it. A regression that
        # constructed a new client per request would burn
        # connection pools.
        sentinel = MagicMock(name="redis-client")
        req = MagicMock()
        req.state.redis = sentinel
        assert await get_redis(req) is sentinel


class TestExports:
    def test_all_exports_present(self) -> None:
        assert set(R.__all__) == {"Redis", "create_redis", "get_redis"}
