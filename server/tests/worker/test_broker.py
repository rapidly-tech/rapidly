"""Tests for ``rapidly/worker/_broker.py``.

Dramatiq broker assembly. Six load-bearing surfaces:

- ``_DEAD_MESSAGE_TTL_MS`` — 72 h retention for messages that exhaust
  retries, used for production debugging. Drift down loses incident
  evidence; drift up balloons Redis.
- ``_MaxRetriesMiddleware`` resolves retry budget message → actor →
  global default. The order matters: a worker-level cap that
  overrode the actor-level setting would silently double-execute
  flaky tasks. Must precede ``middleware.Retries`` in the stack.
- ``_SchedulerMiddleware.actor_options == {"cron_trigger"}`` — pins
  the option name that Dramatiq must NOT reject; renaming would let
  scheduler-targeted actors silently skip cron registration.
- ``_LogContextMiddleware`` binds + unbinds ``actor_name`` /
  ``message_id`` around each message; cleanup runs on BOTH success
  and skip, otherwise context-vars leak across messages and corrupt
  log attribution.
- ``_LogfireMiddleware.ephemeral_options`` includes the stack key so
  the JSON encoder strips it before Redis persistence (a leaked
  ExitStack would crash JSON encoding).
- ``_build_middleware`` order — infrastructure, then resources, then
  observability, then flow control, then retries-then-limits. The
  ``_MaxRetriesMiddleware`` must precede ``middleware.Retries`` so
  the resolved budget is in place before retry decisions.
"""

from __future__ import annotations

import contextlib
from typing import Any
from unittest.mock import MagicMock

import dramatiq
import structlog
from dramatiq import middleware as dramatiq_middleware

from rapidly.worker._broker import (
    _DEAD_MESSAGE_TTL_MS,
    _LOG_CONTEXT_KEYS,
    _LOGFIRE_OPT_KEY,
    _LogContextMiddleware,
    _LogfireMiddleware,
    _MaxRetriesMiddleware,
    _SchedulerMiddleware,
    scheduler_middleware,
)


class TestDeadMessageTtl:
    def test_pinned_to_72_hours(self) -> None:
        # 72-hour debug retention. Production incident-postmortems
        # rely on dead-letter messages being available for ~3 days.
        assert _DEAD_MESSAGE_TTL_MS == 72 * 3600 * 1000


class TestLogContextKeysPin:
    def test_actor_and_message_id_only(self) -> None:
        # Pin: only these two context vars are bound. Adding more
        # would log-leak request-scoped data into worker logs.
        assert _LOG_CONTEXT_KEYS == ("actor_name", "message_id")


class TestLogfireOptKeyPin:
    def test_logfire_stack_key_pinned(self) -> None:
        # The encoder's ephemeral-key list (which strips this key)
        # is built from ``ephemeral_options``. If the constant
        # diverges from the property's set, the stack object would
        # serialise into Redis and crash JSON encoding.
        assert _LOGFIRE_OPT_KEY == "logfire_stack"


def _make_message(
    *,
    actor_name: str = "x",
    message_id: str = "mid",
    options: dict[str, Any] | None = None,
) -> Any:
    msg = MagicMock(spec=dramatiq.MessageProxy)
    msg.actor_name = actor_name
    msg.message_id = message_id
    msg.options = options if options is not None else {}
    msg.asdict = lambda: {"actor_name": actor_name, "message_id": message_id}
    return msg


def _make_broker(*, actor_options: dict[str, Any] | None = None) -> Any:
    actor = MagicMock()
    actor.options = actor_options or {}
    actor.send = MagicMock()
    broker = MagicMock(spec=dramatiq.Broker)
    broker.get_actor = MagicMock(return_value=actor)
    return broker, actor


class TestMaxRetriesMiddlewareResolution:
    def test_message_option_wins(self) -> None:
        # Pin: per-message ``max_retries`` overrides actor + global.
        # Used by ``actor.send_with_options(max_retries=...)`` callers
        # who need a one-off budget bump.
        broker, _ = _make_broker(actor_options={"max_retries": 5})
        msg = _make_message(options={"max_retries": 99})
        _MaxRetriesMiddleware().before_process_message(broker, msg)
        assert msg.options["max_retries"] == 99

    def test_actor_option_wins_when_message_unset(self) -> None:
        # When the message doesn't carry a budget, the actor's
        # declared ``max_retries`` applies (per-actor SLA tuning).
        broker, _ = _make_broker(actor_options={"max_retries": 5})
        msg = _make_message(options={})
        _MaxRetriesMiddleware().before_process_message(broker, msg)
        assert msg.options["max_retries"] == 5

    def test_settings_default_when_none_set(self) -> None:
        # Pin: when neither message nor actor sets a budget, the
        # global ``WORKER_MAX_RETRIES`` setting is used. This keeps
        # the legacy behaviour of Dramatiq for un-annotated actors.
        from rapidly.config import settings

        broker, _ = _make_broker(actor_options={})
        msg = _make_message(options={})
        _MaxRetriesMiddleware().before_process_message(broker, msg)
        assert msg.options["max_retries"] == settings.WORKER_MAX_RETRIES


class TestSchedulerMiddleware:
    def test_actor_option_name_pinned(self) -> None:
        # Pin: Dramatiq rejects unknown actor options unless declared
        # via ``actor_options``. The name ``cron_trigger`` is what
        # decorators pass and what ``scheduler.py`` reads.
        sm = _SchedulerMiddleware()
        assert sm.actor_options == {"cron_trigger"}

    def test_after_declare_actor_collects_triggers(self) -> None:
        # Pin: actors with a ``cron_trigger`` option get registered
        # for APScheduler; actors without the option are ignored.
        sm = _SchedulerMiddleware()
        broker = MagicMock(spec=dramatiq.Broker)

        actor_with = MagicMock()
        actor_with.options = {"cron_trigger": "every-5m"}
        actor_with.send = MagicMock()

        actor_without = MagicMock()
        actor_without.options = {}
        actor_without.send = MagicMock()

        sm.after_declare_actor(broker, actor_with)
        sm.after_declare_actor(broker, actor_without)

        assert len(sm.cron_triggers) == 1
        callable_, trigger = sm.cron_triggers[0]
        assert callable_ is actor_with.send
        assert trigger == "every-5m"

    def test_module_singleton_is_shared(self) -> None:
        # Pin: ``scheduler_middleware`` is the module singleton so
        # the broker AND ``scheduler.py`` see the same registration
        # set. A regression that re-instantiated it would leave the
        # scheduler with zero registered jobs.
        from rapidly.worker import _broker as M

        assert M.scheduler_middleware is scheduler_middleware
        assert isinstance(scheduler_middleware, _SchedulerMiddleware)


class TestLogContextMiddleware:
    def test_before_binds_actor_and_message_id(self) -> None:
        structlog.contextvars.clear_contextvars()
        broker, _ = _make_broker()
        msg = _make_message(actor_name="A", message_id="M1")
        _LogContextMiddleware().before_process_message(broker, msg)
        ctx = structlog.contextvars.get_contextvars()
        assert ctx["actor_name"] == "A"
        assert ctx["message_id"] == "M1"
        structlog.contextvars.clear_contextvars()

    def test_after_process_message_unbinds(self) -> None:
        # Pin: success-path cleanup. Without it, ``actor_name`` from
        # task #1 leaks into log lines for unrelated work between
        # messages.
        structlog.contextvars.clear_contextvars()
        broker, _ = _make_broker()
        msg = _make_message()
        mw = _LogContextMiddleware()
        mw.before_process_message(broker, msg)
        mw.after_process_message(broker, msg)
        ctx = structlog.contextvars.get_contextvars()
        assert "actor_name" not in ctx
        assert "message_id" not in ctx

    def test_after_skip_message_unbinds(self) -> None:
        # Pin: skip-path cleanup. Without it, a debounced/dropped
        # message would leak its actor_name into the next message's
        # log lines (and Sentry crashes).
        structlog.contextvars.clear_contextvars()
        broker, _ = _make_broker()
        msg = _make_message()
        mw = _LogContextMiddleware()
        mw.before_process_message(broker, msg)
        mw.after_skip_message(broker, msg)
        ctx = structlog.contextvars.get_contextvars()
        assert "actor_name" not in ctx
        assert "message_id" not in ctx


class TestLogfireMiddleware:
    def test_ephemeral_options_includes_stack_key(self) -> None:
        # Pin: the encoder strips this key before Redis persistence.
        # If ``ephemeral_options`` doesn't include it, the ExitStack
        # object would be JSON-encoded — and crash, since stacks
        # are not JSON-serialisable.
        mw = _LogfireMiddleware()
        assert _LOGFIRE_OPT_KEY in mw.ephemeral_options

    def test_after_process_message_closes_stack(self) -> None:
        # Pin: success-path cleanup. The stored ``ExitStack`` MUST
        # be closed; leaking it would leave a Logfire span open
        # forever and corrupt distributed-trace ancestry.
        broker, _ = _make_broker()
        stack = contextlib.ExitStack()
        closed: list[bool] = []

        class _Sentinel:
            def __exit__(self, *a: object) -> None:
                closed.append(True)

            def __enter__(self) -> None:
                return None

        stack.enter_context(_Sentinel())
        msg = _make_message(options={_LOGFIRE_OPT_KEY: stack})
        _LogfireMiddleware().after_process_message(broker, msg)
        assert closed == [True]
        # And the option is removed so the encoder never sees it.
        assert _LOGFIRE_OPT_KEY not in msg.options

    def test_after_skip_message_closes_stack(self) -> None:
        # Pin: skip-path cleanup. Same reasoning — a debounced span
        # must close, otherwise the trace is corrupt.
        broker, _ = _make_broker()
        stack = contextlib.ExitStack()
        closed: list[bool] = []

        class _Sentinel:
            def __exit__(self, *a: object) -> None:
                closed.append(True)

            def __enter__(self) -> None:
                return None

        stack.enter_context(_Sentinel())
        msg = _make_message(options={_LOGFIRE_OPT_KEY: stack})
        _LogfireMiddleware().after_skip_message(broker, msg)
        assert closed == [True]
        assert _LOGFIRE_OPT_KEY not in msg.options

    def test_close_span_no_op_when_key_missing(self) -> None:
        # Defensive: cleanup must NOT crash if the key isn't there
        # (e.g., a different middleware skipped the before-hook).
        broker, _ = _make_broker()
        msg = _make_message(options={})  # no _LOGFIRE_OPT_KEY
        _LogfireMiddleware().after_process_message(broker, msg)
        # No exception; option still absent.
        assert _LOGFIRE_OPT_KEY not in msg.options


class TestBuildMiddlewareOrder:
    def test_max_retries_precedes_retries(self) -> None:
        # Pin the comment in ``_build_middleware``: "MaxRetries must
        # precede Retries". A regression that swapped the order would
        # cause Retries to read the un-resolved budget (settings
        # default) before MaxRetries had a chance to override it.
        from rapidly.worker._broker import _build_middleware

        pool = MagicMock()
        stack = _build_middleware(pool)
        types = [type(m) for m in stack]
        max_retries_idx = types.index(_MaxRetriesMiddleware)
        retries_idx = types.index(dramatiq_middleware.Retries)
        assert max_retries_idx < retries_idx

    def test_observability_layers_precede_flow_control(self) -> None:
        # Pin: log/Logfire/Prometheus run BEFORE DebounceMiddleware
        # so a debounce-skip is still attributed to the right
        # actor in dashboards.
        from rapidly.worker._broker import _build_middleware
        from rapidly.worker._debounce import DebounceMiddleware

        pool = MagicMock()
        stack = _build_middleware(pool)
        types = [type(m) for m in stack]
        log_idx = types.index(_LogContextMiddleware)
        logfire_idx = types.index(_LogfireMiddleware)
        debounce_idx = types.index(DebounceMiddleware)
        assert log_idx < debounce_idx
        assert logfire_idx < debounce_idx

    def test_resource_middlewares_present(self) -> None:
        # Pin: SQLAlchemy / Redis / HTTPX / Health middlewares all
        # exist in the stack. Dropping one means worker tasks lose
        # access to its lifecycle hooks (e.g. SQLAlchemy session
        # would never get created → every actor crashes).
        from rapidly.worker._broker import _build_middleware
        from rapidly.worker._health import HealthMiddleware
        from rapidly.worker._httpx import HTTPXMiddleware
        from rapidly.worker._redis import RedisMiddleware
        from rapidly.worker._sqlalchemy import SQLAlchemyMiddleware

        pool = MagicMock()
        types = [type(m) for m in _build_middleware(pool)]
        for required in (
            SQLAlchemyMiddleware,
            RedisMiddleware,
            HTTPXMiddleware,
            HealthMiddleware,
        ):
            assert required in types
