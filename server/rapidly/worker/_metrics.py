"""Dramatiq middleware that records per-task Prometheus metrics.

Instruments every processed message with execution duration and
outcome (success / failure / skipped), and counts retries separately
so that flaky actors are easy to spot in dashboards.
"""

from __future__ import annotations

import time
from typing import Any, Final

import dramatiq

from rapidly.observability import (
    TASK_DURATION,
    TASK_EXECUTIONS,
    TASK_RETRIES,
    register_gc_metrics,
)
from rapidly.observability.remote_write import start_remote_write_pusher

_OPT_KEY: Final[str] = "prom_timer_ns"
_FALLBACK_QUEUE: Final[str] = "default"


class PrometheusMiddleware(dramatiq.Middleware):
    """Collects task timing, outcome, and retry metrics."""

    @property
    def ephemeral_options(self) -> set[str]:
        return {_OPT_KEY}

    # -- Worker boot: one-time setup ----------------------------------------

    def before_worker_boot(
        self, broker: dramatiq.Broker, worker: dramatiq.Worker
    ) -> None:
        # Counter .db files are created at import time, so clearing the
        # prom directory here would silently lose their backing stores.
        start_remote_write_pusher()
        register_gc_metrics()

    # -- Per-message hooks --------------------------------------------------

    def before_process_message(
        self, broker: dramatiq.Broker, message: dramatiq.MessageProxy
    ) -> None:
        message.options[_OPT_KEY] = time.perf_counter()

        retry_count = message.options.get("retries", 0)
        if retry_count > 0:
            q = message.queue_name or _FALLBACK_QUEUE
            TASK_RETRIES.labels(queue=q, task_name=message.actor_name).inc()

    def after_process_message(
        self,
        broker: dramatiq.Broker,
        message: dramatiq.MessageProxy,
        *,
        result: Any | None = None,
        exception: BaseException | None = None,
    ) -> None:
        q = message.queue_name or _FALLBACK_QUEUE
        self._observe_duration(message, q)
        outcome = "failure" if exception else "success"
        TASK_EXECUTIONS.labels(
            queue=q, task_name=message.actor_name, status=outcome
        ).inc()

    def after_skip_message(
        self, broker: dramatiq.Broker, message: dramatiq.MessageProxy
    ) -> None:
        q = message.queue_name or _FALLBACK_QUEUE
        self._observe_duration(message, q)
        TASK_EXECUTIONS.labels(
            queue=q, task_name=message.actor_name, status="skipped"
        ).inc()

    # -- Internal -----------------------------------------------------------

    @staticmethod
    def _observe_duration(message: dramatiq.MessageProxy, queue: str) -> None:
        started: float | None = message.options.pop(_OPT_KEY, None)
        if started is not None:
            TASK_DURATION.labels(queue=queue, task_name=message.actor_name).observe(
                time.perf_counter() - started
            )
