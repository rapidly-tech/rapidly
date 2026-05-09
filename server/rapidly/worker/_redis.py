"""Dramatiq middleware that manages a shared Redis connection for workers."""

import dramatiq
import structlog
from dramatiq.asyncio import get_event_loop_thread

from rapidly.logging import Logger
from rapidly.redis import Redis, create_redis

_log: Logger = structlog.get_logger(__name__)

_REDIS_APP_NAME = "worker"
_conn: Redis | None = None


async def _teardown_redis() -> None:
    global _conn
    if _conn is not None:
        await _conn.close(True)
        _log.info("Redis connection closed")
        _conn = None


class RedisMiddleware(dramatiq.Middleware):
    """Lifecycle middleware for a shared Redis connection."""

    @classmethod
    def get(cls) -> Redis:
        if _conn is None:
            raise RuntimeError("Redis connection has not been initialised")
        return _conn

    def before_worker_boot(
        self, broker: dramatiq.Broker, worker: dramatiq.Worker
    ) -> None:
        global _conn
        _conn = create_redis(_REDIS_APP_NAME)  # type: ignore[arg-type]
        _log.info("Redis connection created")

    def after_worker_shutdown(
        self, broker: dramatiq.Broker, worker: dramatiq.Worker
    ) -> None:
        loop_thread = get_event_loop_thread()
        assert loop_thread is not None
        loop_thread.run_coroutine(_teardown_redis())
