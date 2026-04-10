"""Rapidly background task infrastructure.

Configures a Dramatiq broker backed by Redis, wires up the middleware
stack, and exposes the ``@actor`` decorator plus helpers for dispatching
jobs and managing retry state from within running tasks.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from typing import Any, ParamSpec

import dramatiq
from apscheduler.triggers.cron import CronTrigger
from dramatiq import actor as _raw_actor
from dramatiq import middleware as _mw

from rapidly.config import settings

# Prometheus multiprocess directory MUST be configured before the
# prometheus_client package is first imported anywhere in the process.
from rapidly.observability import metrics as _ensure_prom_dir  # noqa: F401

from ._broker import get_broker
from ._encoder import JSONEncoder
from ._enqueue import (
    BulkJobDelayCalculator,
    JobQueueManager,
    dispatch_task,
    enqueue_events,
    make_bulk_job_delay_calculator,
)
from ._httpx import HTTPXMiddleware
from ._queues import TaskPriority, TaskQueue
from ._redis import RedisMiddleware
from ._sqlalchemy import AsyncSessionMaker

# ---------------------------------------------------------------------------
# Broker initialisation (runs once at import time)
# ---------------------------------------------------------------------------

broker = get_broker()
dramatiq.set_broker(broker)
dramatiq.set_encoder(JSONEncoder(broker))

# ---------------------------------------------------------------------------
# Active-message introspection helpers
# ---------------------------------------------------------------------------

P = ParamSpec("P")


def _active_message() -> dramatiq.MessageProxy:
    """Retrieve the Dramatiq message currently being processed.

    Raises ``AssertionError`` when called outside of a task handler.
    """
    proxy = _mw.CurrentMessage.get_current_message()
    assert proxy is not None, "Called outside of a Dramatiq task handler"
    return proxy  # type: ignore[return-value]


def get_retries() -> int:
    """How many times the current message has been retried so far."""
    return _active_message().options.get("retries", 0)


def can_retry() -> bool:
    """Whether the current message still has retry budget remaining."""
    proxy = _active_message()
    ceiling = proxy.options.get("max_retries", settings.WORKER_MAX_RETRIES)
    return get_retries() < ceiling


# ---------------------------------------------------------------------------
# Queue routing
# ---------------------------------------------------------------------------

_QUEUE_FOR_PRIORITY: dict[TaskPriority, TaskQueue] = {
    TaskPriority.HIGH: TaskQueue.HIGH_PRIORITY,
    TaskPriority.MEDIUM: TaskQueue.MEDIUM_PRIORITY,
    TaskPriority.LOW: TaskQueue.LOW_PRIORITY,
}


# ---------------------------------------------------------------------------
# Actor decorator
# ---------------------------------------------------------------------------


def actor[**P, R](
    actor_class: Callable[..., dramatiq.Actor[Any, Any]] = dramatiq.Actor,
    actor_name: str | None = None,
    queue_name: TaskQueue | None = None,
    priority: TaskPriority = TaskPriority.LOW,
    broker: dramatiq.Broker | None = None,
    **options: Any,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Register an async function as a Dramatiq actor.

    The decorated function is wrapped so that a :class:`JobQueueManager`
    context is active for the entire execution, allowing nested
    ``dispatch_task`` calls to be batched.
    """
    target_queue = (
        queue_name if queue_name is not None else _QUEUE_FOR_PRIORITY[priority]
    )

    def _wrap(fn: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(fn)
        async def _with_job_context(*args: P.args, **kwargs: P.kwargs) -> R:
            async with JobQueueManager.open(
                dramatiq.get_broker(), RedisMiddleware.get()
            ):
                return await fn(*args, **kwargs)

        _raw_actor(  # type: ignore[call-overload]
            _with_job_context,
            actor_class=actor_class,
            actor_name=actor_name,
            queue_name=target_queue,
            priority=priority,
            broker=broker,
            **options,
        )
        return _with_job_context

    return _wrap


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

__all__ = [
    "AsyncSessionMaker",
    "BulkJobDelayCalculator",
    "CronTrigger",
    "HTTPXMiddleware",
    "JobQueueManager",
    "RedisMiddleware",
    "TaskPriority",
    "TaskQueue",
    "actor",
    "can_retry",
    "dispatch_task",
    "enqueue_events",
    "get_retries",
    "make_bulk_job_delay_calculator",
]
