"""Tests for ``rapidly/worker/__init__.py``.

The worker package exports the ``@actor`` decorator + the
introspection helpers running tasks call on themselves
(``get_retries`` / ``can_retry``). The retry helpers read off the
Dramatiq ``CurrentMessage`` proxy — wrong defaults here would make
tasks either give up too early or retry forever.

Pins:
- ``_active_message`` asserts when no message is current — calling
  the helpers outside a task is a programming error, not a missing-
  data path
- ``get_retries`` defaults to 0 (first attempt has no ``retries``
  key in options yet)
- ``can_retry`` falls back to ``settings.WORKER_MAX_RETRIES`` when
  the message doesn't override it — the global retry budget
- ``_QUEUE_FOR_PRIORITY`` map pins each TaskPriority → TaskQueue
- Public surface (``__all__``) covers the documented helpers
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from rapidly.config import settings
from rapidly.worker import (
    _QUEUE_FOR_PRIORITY,
    TaskPriority,
    TaskQueue,
    _active_message,
    can_retry,
    get_retries,
)


def _proxy_with_options(**options: Any) -> MagicMock:
    proxy = MagicMock()
    proxy.options = options
    return proxy


class TestActiveMessageGuard:
    def test_asserts_when_no_current_message(self) -> None:
        # Outside a task handler, ``CurrentMessage.get_current_message``
        # returns None and the helper must crash loudly.
        with patch(
            "dramatiq.middleware.CurrentMessage.get_current_message",
            return_value=None,
        ):
            with pytest.raises(AssertionError, match="outside of a Dramatiq"):
                _active_message()

    def test_returns_proxy_when_message_present(self) -> None:
        proxy = _proxy_with_options(retries=3)
        with patch(
            "dramatiq.middleware.CurrentMessage.get_current_message",
            return_value=proxy,
        ):
            assert _active_message() is proxy


class TestGetRetries:
    def test_returns_zero_when_no_retries_key(self) -> None:
        # Default — Dramatiq doesn't add ``retries`` to options
        # until the second attempt. First attempt must report 0.
        proxy = _proxy_with_options()
        with patch(
            "dramatiq.middleware.CurrentMessage.get_current_message",
            return_value=proxy,
        ):
            assert get_retries() == 0

    def test_returns_options_retries_value(self) -> None:
        proxy = _proxy_with_options(retries=5)
        with patch(
            "dramatiq.middleware.CurrentMessage.get_current_message",
            return_value=proxy,
        ):
            assert get_retries() == 5


class TestCanRetry:
    def test_falls_back_to_settings_max_retries(self) -> None:
        # Without a per-message override, the global ceiling
        # determines whether the actor can retry.
        proxy = _proxy_with_options(retries=settings.WORKER_MAX_RETRIES - 1)
        with patch(
            "dramatiq.middleware.CurrentMessage.get_current_message",
            return_value=proxy,
        ):
            assert can_retry() is True

    def test_returns_false_when_at_settings_ceiling(self) -> None:
        proxy = _proxy_with_options(retries=settings.WORKER_MAX_RETRIES)
        with patch(
            "dramatiq.middleware.CurrentMessage.get_current_message",
            return_value=proxy,
        ):
            assert can_retry() is False

    def test_per_message_override_respected(self) -> None:
        # An actor declared with ``max_retries=2`` overrides the
        # global ceiling — pinning prevents a regression that
        # ignored the override.
        proxy = _proxy_with_options(retries=1, max_retries=2)
        with patch(
            "dramatiq.middleware.CurrentMessage.get_current_message",
            return_value=proxy,
        ):
            assert can_retry() is True

    def test_per_message_override_rejects_when_exceeded(self) -> None:
        proxy = _proxy_with_options(retries=2, max_retries=2)
        with patch(
            "dramatiq.middleware.CurrentMessage.get_current_message",
            return_value=proxy,
        ):
            assert can_retry() is False


class TestQueueForPriorityMap:
    def test_each_priority_has_a_queue(self) -> None:
        # The actor decorator falls back to this map when
        # ``queue_name`` isn't supplied. Pinning prevents a
        # silent absence (which would KeyError every default
        # actor registration).
        assert _QUEUE_FOR_PRIORITY == {
            TaskPriority.HIGH: TaskQueue.HIGH_PRIORITY,
            TaskPriority.MEDIUM: TaskQueue.MEDIUM_PRIORITY,
            TaskPriority.LOW: TaskQueue.LOW_PRIORITY,
        }

    def test_every_priority_member_present(self) -> None:
        for priority in TaskPriority:
            assert priority in _QUEUE_FOR_PRIORITY


class TestPublicSurface:
    def test_all_documented_names_exported(self) -> None:
        from rapidly import worker as W

        expected = {
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
        }
        assert set(W.__all__) == expected
