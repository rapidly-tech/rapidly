"""Tests for ``rapidly/observability/metrics.py``.

Worker-subsystem metrics. Five load-bearing surfaces:

- Prometheus instrument names (``rapidly_task_executions_total``,
  ``rapidly_task_duration_seconds``, ``rapidly_task_retries_total``,
  ``rapidly_task_debounced_total``, ``rapidly_task_debounce_delay_seconds``,
  ``rapidly_gc_collection_seconds``) — Grafana panels and worker-throughput
  alerts query the literal names; rename = silent breakage
- Histogram bucket boundaries — TASK_DURATION (0.1s..120s) covers fast
  inline jobs through the slowest legit batch; TASK_DEBOUNCE_DELAY
  (1s..3600s) brackets the debounce window; GC_COLLECTION_DURATION
  (0.001s..5s) covers both fast Gen0 sweeps and slow Gen2 pauses
- ``_on_gc_phase`` records a timestamp on ``start`` and observes the
  delta on ``stop`` — drift here would silently lose GC-pause signal
  and mask GIL-blocking issues
- ``register_gc_metrics`` is idempotent — re-importing the module or
  calling the registrar twice must NOT install duplicate callbacks
  (which would cause double-counted observations)
- The ``stop``-without-``start`` path is a silent no-op (defensive
  against partial-state observation when the callback is registered
  mid-cycle)
"""

from __future__ import annotations

import gc

from prometheus_client import Counter, Histogram

from rapidly.observability import metrics as M
from rapidly.observability.metrics import (
    GC_COLLECTION_DURATION,
    TASK_DEBOUNCE_DELAY,
    TASK_DEBOUNCED,
    TASK_DURATION,
    TASK_EXECUTIONS,
    TASK_RETRIES,
    _on_gc_phase,
    register_gc_metrics,
)


def _bucket_upper_bounds(hist: Histogram, **labels: str) -> list[float]:
    return sorted(
        float(s.labels["le"])
        for m in hist.collect()
        for s in m.samples
        if s.name.endswith("_bucket") and s.labels.get("le") not in (None, "+Inf")
    )


class TestTaskExecutionsCounter:
    def test_metric_type(self) -> None:
        assert isinstance(TASK_EXECUTIONS, Counter)

    def test_label_arity(self) -> None:
        # Adding/removing a label is a breaking change for PromQL —
        # alert thresholds and dashboard panels assume exactly these
        # three labels.
        before = TASK_EXECUTIONS.labels(
            queue="default", task_name="x", status="success"
        )._value.get()
        TASK_EXECUTIONS.labels(queue="default", task_name="x", status="success").inc()
        after = TASK_EXECUTIONS.labels(
            queue="default", task_name="x", status="success"
        )._value.get()
        assert after == before + 1


class TestTaskDurationHistogram:
    def test_metric_type(self) -> None:
        assert isinstance(TASK_DURATION, Histogram)

    def test_bucket_lower_bound_is_100ms(self) -> None:
        # 100ms floor — fast inline jobs need a meaningful bucket. A
        # regression to 1.0s would group every fast task together and
        # destroy fast-path latency signal.
        bounds = _bucket_upper_bounds(TASK_DURATION, queue="default", task_name="probe")
        # Touch a labelled series to materialise samples.
        TASK_DURATION.labels(queue="default", task_name="probe").observe(0.05)
        bounds = _bucket_upper_bounds(TASK_DURATION, queue="default", task_name="probe")
        assert bounds[0] <= 0.1

    def test_bucket_upper_bound_is_two_minutes(self) -> None:
        # 120s upper bound covers the slowest legit batch task. A
        # regression that capped at 30s would dump every long-running
        # job into ``+Inf`` and lose tail-latency signal.
        TASK_DURATION.labels(queue="default", task_name="probe-upper").observe(0.05)
        bounds = _bucket_upper_bounds(
            TASK_DURATION, queue="default", task_name="probe-upper"
        )
        assert max(bounds) >= 120.0


class TestTaskRetriesCounter:
    def test_metric_type(self) -> None:
        assert isinstance(TASK_RETRIES, Counter)


class TestTaskDebouncedCounter:
    def test_metric_type(self) -> None:
        assert isinstance(TASK_DEBOUNCED, Counter)


class TestTaskDebounceDelayHistogram:
    def test_metric_type(self) -> None:
        assert isinstance(TASK_DEBOUNCE_DELAY, Histogram)

    def test_bucket_upper_bound_is_one_hour(self) -> None:
        # Debounce can hold tasks up to the longest documented window
        # (1 hour). A regression that capped at e.g. 5 min would
        # silently mis-bucket every debounced batch as ``+Inf``.
        TASK_DEBOUNCE_DELAY.labels(queue="default", task_name="probe-deb").observe(0.5)
        bounds = _bucket_upper_bounds(
            TASK_DEBOUNCE_DELAY, queue="default", task_name="probe-deb"
        )
        assert max(bounds) >= 3600.0


class TestGcCollectionHistogram:
    def test_metric_type(self) -> None:
        assert isinstance(GC_COLLECTION_DURATION, Histogram)

    def test_bucket_lower_bound_is_one_millisecond(self) -> None:
        # 1ms floor — fast Gen0 sweeps fall here. A regression that
        # raised the floor (e.g. 10ms) would group every fast GC
        # together and lose the signal that p99 GC is healthy.
        GC_COLLECTION_DURATION.labels(generation="0").observe(0.0005)
        bounds = _bucket_upper_bounds(GC_COLLECTION_DURATION, generation="0")
        assert bounds[0] <= 0.001

    def test_bucket_upper_bound_covers_slow_gen2(self) -> None:
        # 5s upper bound. Slow Gen2 collection pauses on a busy worker
        # can take seconds; tighter than 5s would lose the worst-case
        # GIL-blocking signal.
        GC_COLLECTION_DURATION.labels(generation="2").observe(0.0005)
        bounds = _bucket_upper_bounds(GC_COLLECTION_DURATION, generation="2")
        assert max(bounds) >= 5.0


class TestOnGcPhase:
    def setup_method(self) -> None:
        M._gc_state.clear()

    def teardown_method(self) -> None:
        M._gc_state.clear()

    def test_start_records_timestamp(self) -> None:
        # ``start`` must populate the sentinel-keyed timestamp so the
        # subsequent ``stop`` can compute a duration.
        _on_gc_phase("start", {"generation": 0})
        assert M._GC_PHASE_STARTED_AT in M._gc_state

    def test_stop_observes_a_positive_duration(self) -> None:
        # End-to-end pin: a start/stop pair MUST produce a Histogram
        # observation. Regression to e.g. ``observe(0)`` would silently
        # blank out the GC dashboard.
        before = GC_COLLECTION_DURATION.labels(generation="1")._sum.get()
        _on_gc_phase("start", {"generation": 1})
        _on_gc_phase("stop", {"generation": 1})
        after = GC_COLLECTION_DURATION.labels(generation="1")._sum.get()
        assert after > before

    def test_stop_clears_the_state(self) -> None:
        # Pin: after ``stop``, the sentinel key is removed so a stray
        # second ``stop`` doesn't double-count.
        _on_gc_phase("start", {"generation": 0})
        _on_gc_phase("stop", {"generation": 0})
        assert M._GC_PHASE_STARTED_AT not in M._gc_state

    def test_stop_without_prior_start_is_noop(self) -> None:
        # Defensive: callback registered mid-cycle may see a ``stop``
        # with no preceding ``start``. Pin the silent-no-op behaviour
        # so that a regression to e.g. crashing on KeyError doesn't
        # break the worker boot.
        before = GC_COLLECTION_DURATION.labels(generation="0")._sum.get()
        _on_gc_phase("stop", {"generation": 0})
        after = GC_COLLECTION_DURATION.labels(generation="0")._sum.get()
        assert after == before

    def test_unknown_phase_is_noop(self) -> None:
        # Future Python releases may add new GC phase strings. The
        # callback must ignore them silently rather than crash —
        # crashing inside a GC callback corrupts CPython internals.
        _on_gc_phase("future-phase", {"generation": 0})
        assert M._GC_PHASE_STARTED_AT not in M._gc_state


class TestRegisterGcMetrics:
    def setup_method(self) -> None:
        # Snapshot original callbacks; restore in teardown.
        self._orig = list(gc.callbacks)
        # Remove any pre-existing _on_gc_phase callbacks for a clean test.
        while _on_gc_phase in gc.callbacks:
            gc.callbacks.remove(_on_gc_phase)

    def teardown_method(self) -> None:
        # Restore: drop any test-installed _on_gc_phase, then re-add
        # the originals.
        while _on_gc_phase in gc.callbacks:
            gc.callbacks.remove(_on_gc_phase)
        gc.callbacks[:] = self._orig

    def test_installs_callback(self) -> None:
        assert _on_gc_phase not in gc.callbacks
        register_gc_metrics()
        assert _on_gc_phase in gc.callbacks

    def test_is_idempotent(self) -> None:
        # Pin: re-importing the worker bootstrap or calling the
        # registrar twice must NOT install duplicate callbacks.
        # Otherwise every GC phase would trigger two observations
        # and double-count the histogram (silent dashboard distortion).
        register_gc_metrics()
        register_gc_metrics()
        assert gc.callbacks.count(_on_gc_phase) == 1
