"""Job queue manager: batches enqueued jobs and flushes them to Redis atomically.

All ``dispatch_task`` / ``enqueue_events`` calls made within a single
request or worker invocation are collected by a ``JobQueueManager``
stored in a ``contextvars.ContextVar``.  On successful completion the
entire batch is flushed to Redis in one pipeline call.
"""

import contextlib
import contextvars
import itertools
import time
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator, Callable, Iterable, Mapping
from typing import Any, Self

import dramatiq
import structlog
from dramatiq.common import dq_name

from rapidly.logging import Logger
from rapidly.redis import Redis

from ._debounce import set_debounce_key

_log: Logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

type JSONSerializable = (
    Mapping[str, "JSONSerializable"]
    | Iterable["JSONSerializable"]
    | str
    | int
    | float
    | bool
    | uuid.UUID
    | None
)


# ---------------------------------------------------------------------------
# Context variable
# ---------------------------------------------------------------------------

_job_queue_manager: contextvars.ContextVar["JobQueueManager | None"] = (
    contextvars.ContextVar("rapidly.job_queue_manager")
)

# Max messages per Redis pipeline call to avoid huge payloads.
_FLUSH_BATCH_SIZE: int = 50


def _now_millis() -> int:
    return int(time.time() * 1000)


# ---------------------------------------------------------------------------
# Core manager
# ---------------------------------------------------------------------------


class JobQueueManager:
    """Collects jobs during a request and flushes them to Redis at the end."""

    __slots__ = ("_pending_events", "_pending_jobs")

    def __init__(self) -> None:
        self._pending_jobs: list[
            tuple[
                str,
                tuple[JSONSerializable, ...],
                dict[str, JSONSerializable],
                int | None,
            ]
        ] = []
        self._pending_events: list[uuid.UUID] = []

    # -- public mutators --

    def dispatch_task(
        self,
        actor: str,
        *args: JSONSerializable,
        delay: int | None = None,
        **kwargs: JSONSerializable,
    ) -> None:
        self._pending_jobs.append((actor, args, kwargs, delay))
        _log.debug("job_enqueued", actor=actor, delay=delay)

    def enqueue_events(self, *event_ids: uuid.UUID) -> None:
        self._pending_events.extend(event_ids)

    # -- flush --

    async def flush(self, broker: dramatiq.Broker, redis: Redis) -> None:
        """Serialise pending jobs and push them into Redis."""
        if self._pending_events:
            self.dispatch_task("event.ingested", self._pending_events)

        if not self._pending_jobs:
            self.reset()
            return

        per_queue = defaultdict[str, list[tuple[str, Any]]](list)
        flushed_actors: list[str] = []

        for actor_name, args, kwargs, delay in self._pending_jobs:
            msg = await self._build_message(
                broker, redis, actor_name, args, kwargs, delay
            )
            encoded = msg.encode()
            rid = msg.options["redis_message_id"]
            per_queue[msg.queue_name].append((rid, encoded))
            flushed_actors.append(actor_name)

        for queue_name, messages in per_queue.items():
            for batch in itertools.batched(messages, _FLUSH_BATCH_SIZE):
                await self._push_batch(redis, queue_name, batch)

        for name in flushed_actors:
            _log.debug("job_flushed", actor=name)

        self.reset()

    async def _build_message(
        self,
        broker: dramatiq.Broker,
        redis: Redis,
        actor_name: str,
        args: tuple[JSONSerializable, ...],
        kwargs: dict[str, JSONSerializable],
        delay: int | None,
    ) -> dramatiq.Message:  # type: ignore[type-arg]
        fn: dramatiq.Actor[Any, Any] = broker.get_actor(actor_name)
        rid = str(uuid.uuid4())

        message = fn.message_with_options(
            args=args, kwargs=kwargs, redis_message_id=rid
        )

        # Apply debounce if configured
        debounce = await set_debounce_key(redis, fn, message.message_id, args, kwargs)
        if debounce is not None:
            dkey, ddelay = debounce
            message = message.copy(options={**message.options, "debounce_key": dkey})
            delay = max(delay, ddelay) if delay is not None else ddelay

        # Convert delay to eta on the delayed queue
        if delay is not None and delay > 0:
            eta = _now_millis() + delay
            message = message.copy(
                queue_name=dq_name(message.queue_name),
                options={**message.options, "eta": eta},
            )

        return message

    # -- Redis I/O --

    @staticmethod
    async def _push_batch(
        redis: Redis,
        queue_name: str,
        batch: Iterable[tuple[str, Any]],
    ) -> None:
        items = list(batch)
        hash_key = f"dramatiq:{queue_name}.msgs"
        queue_key = f"dramatiq:{queue_name}"
        await redis.hset(
            hash_key,
            mapping={mid: payload for mid, payload in items},
        )
        await redis.rpush(queue_key, *(mid for mid, _ in items))

    # -- lifecycle --

    def reset(self) -> None:
        self._pending_jobs = []
        self._pending_events = []

    @classmethod
    def set(cls) -> "Self":
        mgr = cls()
        _job_queue_manager.set(mgr)
        return mgr

    @classmethod
    def close(cls) -> None:
        mgr = cls.get()
        mgr.reset()
        _job_queue_manager.set(None)

    @classmethod
    @contextlib.asynccontextmanager
    async def open(cls, broker: dramatiq.Broker, redis: Redis) -> AsyncIterator["Self"]:
        mgr = cls.set()
        try:
            yield mgr
            await mgr.flush(broker, redis)
        finally:
            cls.close()

    @classmethod
    def get(cls) -> "JobQueueManager":
        mgr = _job_queue_manager.get()
        if mgr is None:
            raise RuntimeError("JobQueueManager not initialized")
        return mgr


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------


def dispatch_task(
    actor: str,
    *args: JSONSerializable,
    delay: int | None = None,
    **kwargs: JSONSerializable,
) -> None:
    """Enqueue a job by actor name.

    Args:
        actor: The name of the actor to enqueue.
        *args: Positional arguments to pass to the actor.
        delay: Optional delay in milliseconds before the job is processed.
        **kwargs: Keyword arguments to pass to the actor.
    """
    JobQueueManager.get().dispatch_task(actor, *args, delay=delay, **kwargs)


def enqueue_events(*event_ids: uuid.UUID) -> None:
    """Enqueue events to be ingested."""
    JobQueueManager.get().enqueue_events(*event_ids)


# ---------------------------------------------------------------------------
# Bulk job delay calculator
# ---------------------------------------------------------------------------

type BulkJobDelayCalculator = Callable[[int], int | None]


def _linear_delay(per_item_ms: int) -> BulkJobDelayCalculator:
    """Return a calculator that spaces jobs linearly by *per_item_ms*."""

    def _calc(index: int) -> int | None:
        ms = index * per_item_ms
        return ms or None

    return _calc


def make_bulk_job_delay_calculator(
    total_count: int,
    *,
    target_delay_ms: int = 200,
    min_delay_ms: int = 50,
    max_spread_ms: int = 300_000,
    allow_spill: bool = True,
) -> BulkJobDelayCalculator:
    """Create a delay calculator for bulk job spreading.

    When enqueueing many jobs at once (e.g., sending notifications to all customers
    of an workspace), this function returns a calculator that computes the appropriate
    delay for each job to spread them out over time and prevent queue saturation.

    The delay logic:
    1. If count * target_delay <= max_spread: use target_delay (200ms)
    2. If calculated delay >= min_delay: compress to fit in max_spread
    3. If calculated delay < min_delay:
       - allow_spill=True: use min_delay, accepting that total time exceeds max_spread
       - allow_spill=False: batch items together to stay within max_spread

    Args:
        total_count: The total number of items in the batch.
        target_delay_ms: Target delay between jobs in milliseconds (default: 200).
        min_delay_ms: Minimum delay floor in milliseconds (default: 50).
        max_spread_ms: Maximum total spread time in milliseconds (default: 300,000 = 5 minutes).
        allow_spill: If True, respects min_delay even if total time exceeds max_spread.
            If False, batches items together to stay within max_spread (default: True).

    Returns:
        A function that takes an index and returns the delay in milliseconds,
        or None if no delay is needed (first item).
    """
    # Case 1: fits comfortably
    if total_count * target_delay_ms <= max_spread_ms:
        return _linear_delay(target_delay_ms)

    # Case 2: compress evenly
    compressed = max_spread_ms // total_count
    if compressed >= min_delay_ms:
        return _linear_delay(compressed)

    # Case 3a: allow overflow
    if allow_spill:
        return _linear_delay(min_delay_ms)

    # Case 3b: batch items into fixed-size slots
    # Extra items go to earlier batches: 17 items / 5 slots = 4-4-3-3-3
    num_slots = (max_spread_ms // min_delay_ms) + 1  # +1 for the zero-delay slot
    base_size = total_count // num_slots
    overflow_size = base_size + 1
    overflow_count = total_count % num_slots
    overflow_boundary = overflow_count * overflow_size

    def _batched_delay(index: int) -> int | None:
        if index < overflow_boundary:
            slot = index // overflow_size
        else:
            slot = overflow_count + (index - overflow_boundary) // base_size
        ms = slot * min_delay_ms
        return ms or None

    return _batched_delay
