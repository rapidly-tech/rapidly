"""Async Redis connection management for Rapidly services.

Each process (API server, worker, rate-limiter, script) creates its own
connection pool via ``create_redis``.  The ``get_redis`` dependency
extracts the per-request instance stored on ``request.state`` by the
application lifespan handler.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import redis.asyncio as _redis_async
from fastapi import Request
from redis import ConnectionError as RedisConnectionError
from redis import RedisError
from redis import TimeoutError as RedisTimeoutError
from redis.asyncio.retry import Retry
from redis.backoff import default_backoff

from rapidly.config import settings

# redis-py's type stubs are generic at check time but not at runtime.
# See https://github.com/python/typeshed/issues/7597
if TYPE_CHECKING:
    Redis = _redis_async.Redis[str]
else:
    Redis = _redis_async.Redis

type ProcessName = Literal["app", "rate-limit", "worker", "script"]

_RETRY_LIMIT = 50
_RETRYABLE_ERRORS: tuple[type[RedisError], ...] = (
    RedisConnectionError,
    RedisTimeoutError,
)


def _build_retry_policy() -> Retry:
    return Retry(default_backoff(), retries=_RETRY_LIMIT)


def create_redis(process_name: ProcessName) -> Redis:
    """Construct a new async Redis client with retry-on-transient-error."""
    return _redis_async.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        retry_on_error=list(_RETRYABLE_ERRORS),
        retry=_build_retry_policy(),
        client_name=f"{settings.ENV.value}.{process_name}",
    )


async def get_redis(request: Request) -> Redis:
    """FastAPI dependency — returns the Redis handle from request state."""
    return request.state.redis


__all__ = [
    "Redis",
    "create_redis",
    "get_redis",
]
