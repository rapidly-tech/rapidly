"""Dramatiq broker assembly: Redis transport, middleware stack, and cron scheduling."""

import contextlib
import contextvars
from collections.abc import Callable
from typing import Any, ClassVar

import dramatiq
import logfire
import redis
import structlog
from apscheduler.triggers.cron import CronTrigger
from dramatiq import middleware
from dramatiq.brokers.redis import RedisBroker

from rapidly.config import settings
from rapidly.logfire import instrument_httpx
from rapidly.logging import Logger

from ._debounce import DebounceMiddleware
from ._health import HealthMiddleware
from ._httpx import HTTPXMiddleware
from ._metrics import PrometheusMiddleware
from ._redis import RedisMiddleware
from ._sqlalchemy import SQLAlchemyMiddleware

_log: Logger = structlog.get_logger(__name__)

# Dead-letter TTL: messages that exhaust retries are kept for debugging
_DEAD_MESSAGE_TTL_MS: int = 72 * 3600 * 1000  # 72 hours

# ── Middleware stack ──


class _MaxRetriesMiddleware(dramatiq.Middleware):
    """Resolve per-message retry limits from message → actor → global defaults."""

    def before_process_message(
        self, broker: dramatiq.Broker, message: dramatiq.MessageProxy
    ) -> None:
        actor = broker.get_actor(message.actor_name)
        resolved = message.options.get(
            "max_retries", actor.options.get("max_retries", settings.WORKER_MAX_RETRIES)
        )
        message.options["max_retries"] = resolved


class _SchedulerMiddleware(dramatiq.Middleware):
    """Collect ``cron_trigger`` actor options for APScheduler registration."""

    def __init__(self) -> None:
        self.cron_triggers: list[tuple[Callable[..., Any], CronTrigger]] = []

    @property
    def actor_options(self) -> set[str]:
        return {"cron_trigger"}

    def after_declare_actor(
        self, broker: dramatiq.Broker, actor: dramatiq.Actor[Any, Any]
    ) -> None:
        if trigger := actor.options.get("cron_trigger"):
            self.cron_triggers.append((actor.send, trigger))


scheduler_middleware = _SchedulerMiddleware()


_LOG_CONTEXT_KEYS: tuple[str, ...] = ("actor_name", "message_id")


class _LogContextMiddleware(dramatiq.Middleware):
    """Bind structured-log context vars for the duration of each message."""

    def before_process_message(
        self, broker: dramatiq.Broker, message: dramatiq.MessageProxy
    ) -> None:
        structlog.contextvars.bind_contextvars(
            actor_name=message.actor_name, message_id=message.message_id
        )

    def _cleanup(self) -> None:
        structlog.contextvars.unbind_contextvars(*_LOG_CONTEXT_KEYS)

    def after_process_message(
        self,
        broker: dramatiq.Broker,
        message: dramatiq.MessageProxy,
        *,
        result: Any | None = None,
        exception: BaseException | None = None,
    ) -> None:
        self._cleanup()

    def after_skip_message(
        self, broker: dramatiq.Broker, message: dramatiq.MessageProxy
    ) -> None:
        self._cleanup()


_LOGFIRE_OPT_KEY: str = "logfire_stack"


class _LogfireMiddleware(dramatiq.Middleware):
    """Open a Logfire span around each message for distributed tracing."""

    gc_span: ClassVar[contextvars.ContextVar[contextlib.ExitStack | None]] = (
        contextvars.ContextVar("gc_span", default=None)
    )

    @property
    def ephemeral_options(self) -> set[str]:
        return {_LOGFIRE_OPT_KEY}

    def before_worker_boot(
        self, broker: dramatiq.Broker, worker: dramatiq.Worker
    ) -> None:
        instrument_httpx()

    def before_process_message(
        self, broker: dramatiq.Broker, message: dramatiq.MessageProxy
    ) -> None:
        stack = contextlib.ExitStack()
        name = message.actor_name
        if name in settings.LOGFIRE_IGNORED_ACTORS:
            stack.enter_context(logfire.suppress_instrumentation())
        else:
            stack.enter_context(
                logfire.span("TASK {actor}", actor=name, message=message.asdict())
            )
        message.options[_LOGFIRE_OPT_KEY] = stack

    def _close_span(self, message: dramatiq.MessageProxy) -> None:
        stack: contextlib.ExitStack | None = message.options.pop(_LOGFIRE_OPT_KEY, None)
        if stack is not None:
            stack.close()

    def after_process_message(
        self,
        broker: dramatiq.Broker,
        message: dramatiq.MessageProxy,
        *,
        result: Any | None = None,
        exception: BaseException | None = None,
    ) -> None:
        self._close_span(message)

    def after_skip_message(
        self, broker: dramatiq.Broker, message: dramatiq.MessageProxy
    ) -> None:
        self._close_span(message)


# ── Queue configuration ──


def _build_middleware(pool: redis.ConnectionPool) -> list[dramatiq.Middleware]:
    """Assemble the ordered middleware stack for the broker."""
    return [
        # Infrastructure & async support
        middleware.ShutdownNotifications(),
        middleware.AsyncIO(),
        # Resource lifecycle (worker boot/shutdown)
        SQLAlchemyMiddleware(),
        RedisMiddleware(),
        HTTPXMiddleware(),
        HealthMiddleware(),
        scheduler_middleware,
        # Observability (outer layer for message processing)
        _LogContextMiddleware(),
        _LogfireMiddleware(),
        PrometheusMiddleware(),
        # Message flow control
        DebounceMiddleware(pool),
        # Retry & execution control (_MaxRetries must precede Retries)
        _MaxRetriesMiddleware(),
        middleware.Retries(
            max_retries=settings.WORKER_MAX_RETRIES,
            min_backoff=settings.WORKER_RETRY_BASE_DELAY_MS,
        ),
        middleware.AgeLimit(),
        middleware.TimeLimit(),
        middleware.CurrentMessage(),
    ]


# ── Broker setup ──


def get_broker() -> dramatiq.Broker:
    """Create a Redis-backed Dramatiq broker with the full middleware stack."""
    pool = redis.ConnectionPool.from_url(
        settings.redis_url,
        client_name=f"{settings.ENV.value}.worker.dramatiq",
    )
    return RedisBroker(
        connection_pool=pool,
        middleware=_build_middleware(pool),
        dead_message_ttl=_DEAD_MESSAGE_TTL_MS,
    )


__all__ = [
    "get_broker",
    "scheduler_middleware",
]
