"""Redis-backed debounce mechanism for background tasks.

Coalesces rapid-fire dispatches of the same logical task into a single
execution after a configurable quiet period.  A Redis hash with TTL
serves as the deduplication lock so debounce state survives worker
restarts.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Never

import dramatiq
import redis
import redis.asyncio
import structlog

from rapidly.config import settings
from rapidly.logging import Logger
from rapidly.observability import TASK_DEBOUNCE_DELAY, TASK_DEBOUNCED

if TYPE_CHECKING:
    from ._enqueue import JSONSerializable

    RedisAsyncIO = redis.asyncio.Redis[str]
else:
    RedisAsyncIO = redis.asyncio.Redis

_log: Logger = structlog.get_logger(__name__)

# Fail-safe TTL so keys do not linger in Redis forever.
_KEY_TTL = timedelta(hours=1)

# Prefix applied to all debounce keys.
_KEY_PREFIX = "debounce:"

# For backwards compatibility with external imports.
DEBOUNCE_KEY_TTL = _KEY_TTL
DEBOUNCE_KEY_PREFIX = _KEY_PREFIX


# ---------------------------------------------------------------------------
# Timestamp helper
# ---------------------------------------------------------------------------


def now_timestamp() -> int:
    return int(datetime.now(UTC).timestamp())


# ---------------------------------------------------------------------------
# Key management (async, used at enqueue time)
# ---------------------------------------------------------------------------


async def set_debounce_key(
    redis: RedisAsyncIO,
    actor: dramatiq.Actor[Any, Any],
    message_id: str,
    args: tuple["JSONSerializable", ...],
    kwargs: dict[str, "JSONSerializable"],
) -> tuple[str, int] | None:
    """Write the debounce hash and return ``(key, delay_ms)`` or ``None``."""
    factory: Callable[..., str | None] | None = actor.options.get("debounce_key")
    if factory is None:
        return None

    key_value = factory(*args, **kwargs)
    if key_value is None:
        return None

    full_key = f"{_KEY_PREFIX}{key_value}"
    delay_ms: int = (
        actor.options.get(
            "debounce_min_threshold",
            int(settings.WORKER_DEFAULT_DEBOUNCE_MIN_THRESHOLD.total_seconds()),
        )
        * 1000
    )

    async with redis.pipeline(transaction=True) as pipe:
        await pipe.hsetnx(full_key, "enqueue_timestamp", now_timestamp())
        await pipe.hset(full_key, "message_id", message_id)
        await pipe.hset(full_key, "executed", 0)
        await pipe.expire(full_key, _KEY_TTL)
        await pipe.execute()

    _log.debug("debounce_key_set", key=full_key, delay=delay_ms)
    return full_key, delay_ms


# ---------------------------------------------------------------------------
# Middleware (sync, runs inside the worker)
# ---------------------------------------------------------------------------


class DebounceMiddleware(dramatiq.Middleware):
    """Dramatiq middleware that skips duplicate messages within a debounce window."""

    def __init__(self, redis_pool: redis.ConnectionPool) -> None:
        self._redis = redis.Redis(connection_pool=redis_pool, decode_responses=False)

    # -- option declarations --

    @property
    def actor_options(self) -> set[str]:
        return {"debounce_key", "debounce_min_threshold", "debounce_max_threshold"}

    @property
    def ephemeral_options(self) -> set[str]:
        return {"debounce_enqueue_timestamp"}

    # -- pre-processing --

    def before_process_message(
        self, broker: dramatiq.Broker, message: dramatiq.MessageProxy
    ) -> None:
        debounce_key = message.options.get("debounce_key")
        if debounce_key is None:
            return

        _log.debug("debounce_check", debounce_key=debounce_key)

        data = self._redis.hgetall(debounce_key)
        if not data:
            return

        # Already executed in this window
        if int(data.get(b"executed", 0)):
            _log.debug("debounce_already_executed", debounce_key=debounce_key)
            self._skip(message)

        owner = data[b"message_id"].decode("utf-8")
        enqueue_ts = int(data[b"enqueue_timestamp"])
        message.options["debounce_enqueue_timestamp"] = enqueue_ts

        # Owner always executes
        if owner == message.message_id:
            return

        # Check max threshold
        max_threshold = self._max_threshold(broker, message)
        if enqueue_ts + max_threshold < now_timestamp():
            _log.info(
                "debounce_max_threshold_reached",
                debounce_key=debounce_key,
                owner=owner,
            )
            message.options["debounce_max_threshold_execution"] = True
            return

        _log.info("debounce_not_owner", debounce_key=debounce_key, owner=owner)
        self._skip(message)

    # -- post-processing --

    def after_skip_message(
        self, broker: dramatiq.Broker, message: dramatiq.MessageProxy
    ) -> None:
        message.options.pop("debounce_enqueue_timestamp", None)
        message.options.pop("debounce_max_threshold_execution", None)

    def after_process_message(
        self,
        broker: dramatiq.Broker,
        message: dramatiq.MessageProxy,
        *,
        result: Any = None,
        exception: BaseException | None = None,
    ) -> None:
        debounce_key = message.options.get("debounce_key")
        if debounce_key is None:
            return

        enqueue_ts: int | None = message.options.pop("debounce_enqueue_timestamp")
        if enqueue_ts is not None:
            elapsed = now_timestamp() - enqueue_ts
            q = message.queue_name or "default"
            TASK_DEBOUNCE_DELAY.labels(queue=q, task_name=message.actor_name).observe(
                elapsed
            )

        was_max_threshold = message.options.pop(
            "debounce_max_threshold_execution", False
        )

        with self._redis.pipeline(transaction=True) as pipe:
            if was_max_threshold:
                _log.debug("debounce_bump_timestamp", debounce_key=debounce_key)
                pipe.hset(debounce_key, "enqueue_timestamp", now_timestamp())
                pipe.expire(debounce_key, _KEY_TTL)
            elif exception is None:
                _log.debug("debounce_mark_executed", debounce_key=debounce_key)
                pipe.hset(debounce_key, "executed", 1)
                pipe.hdel(debounce_key, "enqueue_timestamp")
            pipe.execute()

    # -- helpers --

    def _max_threshold(
        self, broker: dramatiq.Broker, message: dramatiq.MessageProxy
    ) -> int:
        actor = broker.get_actor(message.actor_name)
        return message.options.get(
            "debounce_max_threshold",
            actor.options.get(
                "debounce_max_threshold",
                int(settings.WORKER_DEFAULT_DEBOUNCE_MAX_THRESHOLD.total_seconds()),
            ),
        )

    def _skip(self, message: dramatiq.MessageProxy) -> Never:
        q = message.queue_name or "default"
        TASK_DEBOUNCED.labels(queue=q, task_name=message.actor_name).inc()
        raise dramatiq.middleware.SkipMessage()


__all__ = ["DebounceMiddleware", "set_debounce_key"]
