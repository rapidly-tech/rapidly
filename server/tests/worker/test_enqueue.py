"""Tests for ``rapidly/worker/_enqueue.py``.

Job queue manager + bulk-delay calculator. Five load-bearing surfaces:

- ``_FLUSH_BATCH_SIZE = 50`` — Redis pipeline cap. Drift up balloons
  pipeline payloads (latency + memory); drift down increases round-
  trips (throughput regression on bulk dispatch).
- ``JobQueueManager.get`` raises ``RuntimeError`` when no manager is
  set in the context — defensive against a forgotten ``open(...)``
  scope, which would otherwise silently drop every dispatched task.
- ``open`` async-cm sets the context-var, yields, flushes on success,
  and closes on exit — flush MUST run before close so a pending
  enqueue inside the request body actually reaches Redis.
- ``flush`` short-circuits the empty path (``reset()`` only, no
  Redis I/O) and prepends ``event.ingested`` when events are pending.
  Drift either wastes a Redis round-trip or loses event ingestion.
- ``make_bulk_job_delay_calculator`` 4-case logic: comfort, compress,
  spill, batch. Drift in any case mis-spaces bulk jobs and either
  saturates the queue (too tight) or stalls the customer (too loose).
"""

from __future__ import annotations

import contextvars
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from rapidly.worker import _enqueue as M
from rapidly.worker._enqueue import (
    _FLUSH_BATCH_SIZE,
    JobQueueManager,
    _linear_delay,
    _now_millis,
    dispatch_task,
    enqueue_events,
    make_bulk_job_delay_calculator,
)


@pytest.fixture(autouse=True)
def _reset_context_var() -> Any:
    """Run each test in a fresh ContextVar to avoid leakage across tests."""
    ctx = contextvars.copy_context()

    def _run() -> None:
        # Default: clear any manager left by previous test.
        try:
            M._job_queue_manager.set(None)
        except LookupError:
            pass

    ctx.run(_run)
    yield
    try:
        M._job_queue_manager.set(None)
    except LookupError:
        pass


class TestFlushBatchSize:
    def test_pinned_to_50(self) -> None:
        # 50 messages per Redis pipeline call balances payload size
        # (LIST + HSET arguments) against round-trip overhead.
        assert _FLUSH_BATCH_SIZE == 50


class TestNowMillis:
    def test_returns_int_milliseconds(self) -> None:
        # Pin: integer ms epoch — Dramatiq's ``eta`` field expects
        # integer ms; a float would crash the broker on dispatch.
        v = _now_millis()
        assert isinstance(v, int)
        assert v > 1_700_000_000_000  # sanity: post-2023


class TestJobQueueManagerSetGetClose:
    def test_get_raises_when_unset(self) -> None:
        # Pin: a forgotten ``open(...)`` scope must crash loudly
        # rather than silently drop tasks.
        M._job_queue_manager.set(None)
        with pytest.raises(RuntimeError, match="not initialized"):
            JobQueueManager.get()

    def test_set_creates_and_stores_manager(self) -> None:
        mgr = JobQueueManager.set()
        assert isinstance(mgr, JobQueueManager)
        assert JobQueueManager.get() is mgr

    def test_close_resets_and_clears(self) -> None:
        mgr = JobQueueManager.set()
        mgr.dispatch_task("x.task")
        JobQueueManager.close()
        # After close, the context-var is None.
        with pytest.raises(RuntimeError):
            JobQueueManager.get()


class TestDispatchTaskAndEnqueueEvents:
    def test_dispatch_task_appends_to_pending(self) -> None:
        mgr = JobQueueManager.set()
        mgr.dispatch_task("x.task", 1, 2, delay=500, key="value")
        assert mgr._pending_jobs == [("x.task", (1, 2), {"key": "value"}, 500)]

    def test_dispatch_task_default_delay_none(self) -> None:
        mgr = JobQueueManager.set()
        mgr.dispatch_task("y.task")
        assert mgr._pending_jobs == [("y.task", (), {}, None)]

    def test_enqueue_events_extends_pending(self) -> None:
        mgr = JobQueueManager.set()
        a, b = uuid.uuid4(), uuid.uuid4()
        mgr.enqueue_events(a, b)
        assert mgr._pending_events == [a, b]

    def test_module_dispatch_task_routes_to_context_manager(self) -> None:
        # Pin: the bare module-level helper ``dispatch_task`` resolves
        # the manager from the context-var. A regression that used a
        # global instance would lose context isolation across tasks.
        mgr = JobQueueManager.set()
        dispatch_task("z.task", 1, foo="bar")
        assert mgr._pending_jobs == [("z.task", (1,), {"foo": "bar"}, None)]

    def test_module_enqueue_events_routes_to_context_manager(self) -> None:
        mgr = JobQueueManager.set()
        eid = uuid.uuid4()
        enqueue_events(eid)
        assert mgr._pending_events == [eid]


@pytest.mark.asyncio
class TestFlushShortCircuit:
    async def test_empty_pending_resets_without_redis_io(self) -> None:
        # Pin: empty-flush short-circuit. Without it, every request
        # with no enqueues would still perform a Redis round-trip.
        mgr = JobQueueManager.set()
        broker = MagicMock()
        redis = AsyncMock()
        await mgr.flush(broker, redis)
        # No Redis methods were called.
        redis.hset.assert_not_awaited()
        redis.rpush.assert_not_awaited()


@pytest.mark.asyncio
class TestFlushEventsBecomeIngestionTask:
    async def test_pending_events_get_dispatched_as_ingest_task(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: enqueued events are converted into a single
        # ``event.ingested`` task carrying the list of UUIDs. A
        # regression that dispatched one task per event would
        # quadratically inflate Redis ops on bulk uploads.
        mgr = JobQueueManager.set()
        a, b = uuid.uuid4(), uuid.uuid4()
        mgr.enqueue_events(a, b)

        # Patch _build_message to short-circuit — we only care about
        # what dispatch_task ends up appending.
        captured: list[tuple[str, tuple[Any, ...]]] = []

        async def fake_build(self_, broker, redis, actor_name, args, kwargs, delay):  # type: ignore[no-untyped-def]
            captured.append((actor_name, args))
            msg = MagicMock()
            msg.encode.return_value = b"x"
            msg.options = {"redis_message_id": "rid"}
            msg.queue_name = "q"
            return msg

        monkeypatch.setattr(JobQueueManager, "_build_message", fake_build)

        broker = MagicMock()
        redis = AsyncMock()
        await mgr.flush(broker, redis)

        assert captured[0][0] == "event.ingested"
        assert captured[0][1] == ([a, b],)


@pytest.mark.asyncio
class TestOpenAsyncContextManager:
    async def test_set_yield_flush_close_sequence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: open() yields a manager, flushes on exit (so pending
        # tasks reach Redis), and closes (clears the context-var).
        flush_called: list[bool] = []

        async def fake_flush(self_, broker, redis):  # type: ignore[no-untyped-def]
            flush_called.append(True)

        monkeypatch.setattr(JobQueueManager, "flush", fake_flush)

        broker = MagicMock()
        redis = AsyncMock()
        async with JobQueueManager.open(broker, redis) as mgr:
            assert isinstance(mgr, JobQueueManager)
            mgr.dispatch_task("x.task")

        # Flush ran on exit.
        assert flush_called == [True]
        # And close ran — get() now raises.
        with pytest.raises(RuntimeError):
            JobQueueManager.get()

    async def test_close_runs_even_when_body_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: ``close()`` MUST run in the ``finally`` block so a
        # crashed request doesn't leak its manager into the next
        # task in the same async context.
        async def fake_flush(self_, broker, redis):  # type: ignore[no-untyped-def]
            return None

        monkeypatch.setattr(JobQueueManager, "flush", fake_flush)
        broker = MagicMock()
        redis = AsyncMock()
        with pytest.raises(RuntimeError, match="boom"):
            async with JobQueueManager.open(broker, redis):
                raise RuntimeError("boom")
        with pytest.raises(RuntimeError, match="not initialized"):
            JobQueueManager.get()


class TestLinearDelay:
    def test_first_index_yields_none(self) -> None:
        # Pin: the first item has no delay (``ms or None`` returns
        # None for 0). Otherwise the broker would treat it as a
        # delayed message even at zero delay.
        calc = _linear_delay(100)
        assert calc(0) is None

    def test_later_indices_scale_linearly(self) -> None:
        calc = _linear_delay(100)
        assert calc(1) == 100
        assert calc(5) == 500


class TestBulkDelayCase1Comfort:
    def test_uses_target_delay_when_total_fits(self) -> None:
        # 10 items × 200ms = 2000ms ≤ 5min. Each item gets target_delay.
        calc = make_bulk_job_delay_calculator(total_count=10)
        assert calc(0) is None
        assert calc(1) == 200
        assert calc(9) == 1800


class TestBulkDelayCase2Compress:
    def test_compresses_evenly_when_target_exceeds_max_spread(self) -> None:
        # 2000 items × 200ms = 400_000ms > 300_000ms max_spread.
        # Compressed: 300_000 // 2000 = 150ms (>= min_delay_ms=50).
        calc = make_bulk_job_delay_calculator(total_count=2000)
        assert calc(1) == 150


class TestBulkDelayCase3aSpill:
    def test_uses_min_delay_when_compressed_too_small(self) -> None:
        # 10_000 items: compressed = 30ms < 50ms min. allow_spill
        # default → use min_delay (50ms), accepting overrun.
        calc = make_bulk_job_delay_calculator(total_count=10_000, allow_spill=True)
        assert calc(1) == 50
        assert calc(2) == 100


class TestBulkDelayCase3bBatch:
    def test_batches_items_when_spill_disallowed(self) -> None:
        # Pin: when spill disabled, items batch into slots. Slots
        # = (300_000 / 50) + 1 = 6001. With total_count=10_000:
        #   base_size = 10_000 // 6001 = 1
        #   overflow_size = 2
        #   overflow_count = 10_000 % 6001 = 3999
        # Items 0..(3999*2) live in overflow slots (size 2);
        # later items live in base slots (size 1).
        calc = make_bulk_job_delay_calculator(total_count=10_000, allow_spill=False)
        # First two items share slot 0 (delay 0 → None).
        assert calc(0) is None
        assert calc(1) is None
        # Item 2 lands in slot 1 → delay = 50ms.
        assert calc(2) == 50

    def test_small_count_within_max_spread_uses_target(self) -> None:
        # Sanity: tiny batches still pick case 1 (target_delay).
        calc = make_bulk_job_delay_calculator(total_count=5)
        assert calc(0) is None
        assert calc(1) == 200


class TestBulkDelayBoundaryAtCompressThreshold:
    def test_count_exactly_at_compress_floor(self) -> None:
        # max_spread/count = min_delay → still chooses compress branch.
        # 300_000 / 6000 = 50 → exactly at min_delay, so compress.
        calc = make_bulk_job_delay_calculator(total_count=6000)
        assert calc(1) == 50
