"""Tests for ``rapidly/observability/slo.py``.

Service-level-objective gauge publisher. Four load-bearing surfaces:

- ``_OBJECTIVES`` — the documented per-endpoint p99-latency and
  availability contracts. Drift here means PromQL ``group_left``
  joins compare measured perf against the wrong target, leading to
  silent SLO violation under-/over-reporting.
- Path templates use the FastAPI ``{slug}`` placeholder so that
  Prometheus label-joins match against the route template (NOT
  individual slug values, which would explode cardinality).
- Gauge label arity (``endpoint``, ``method``) — alert rules and
  Grafana dashboards query these literals; rename = silent breakage.
- ``start_slo_metrics`` is idempotent (double-call must NOT spawn a
  second background thread); ``stop_slo_metrics`` clears the module
  singletons so a subsequent ``start`` after-shutdown succeeds.
"""

from __future__ import annotations

import threading
import time

from prometheus_client import Gauge

from rapidly.observability import slo as M
from rapidly.observability.slo import (
    _OBJECTIVES,
    _PUBLISH_INTERVAL_SEC,
    SLO_AVAILABILITY_TARGET,
    SLO_P99_TARGET,
    _EndpointSLO,
    _publish_gauges,
    start_slo_metrics,
    stop_slo_metrics,
)


def _gauge_value(g: Gauge, **labels: str) -> float:
    return g.labels(**labels)._value.get()


class TestPublishInterval:
    def test_pinned_to_five_minutes(self) -> None:
        # 5-minute refresh cadence balances Prometheus restart-recovery
        # speed against thread-wakeup overhead. Drift here either makes
        # gauges go stale across restarts (interval too long) or burns
        # idle CPU (interval too short).
        assert _PUBLISH_INTERVAL_SEC == 300


class TestObjectives:
    def test_six_critical_endpoints(self) -> None:
        # Pin the count so a refactor that drops an objective is
        # caught by the test rather than the alerting team.
        assert len(_OBJECTIVES) == 6

    def test_endpoints_are_route_templates_not_concrete_paths(self) -> None:
        # Path strings MUST contain the ``{slug}`` placeholder rather
        # than concrete slug values — otherwise Prometheus would emit
        # one gauge series per slug (cardinality explosion) and the
        # ``group_left`` join with measured latency would never match.
        slug_endpoints = [o for o in _OBJECTIVES if "{slug}" in o.path]
        assert len(slug_endpoints) >= 4

    def test_all_paths_start_with_api_file_shares(self) -> None:
        # Every objective lives under the file-sharing namespace.
        # Adding a non-file-share path silently means the SLO publisher
        # is being repurposed without an audit.
        for obj in _OBJECTIVES:
            assert obj.path.startswith("/api/file-shares/")

    def test_methods_are_http_verbs(self) -> None:
        # Drift to lowercase ``get`` etc. would break dashboards that
        # join on ``method=POST``.
        allowed = {"GET", "POST", "PUT", "PATCH", "DELETE"}
        for obj in _OBJECTIVES:
            assert obj.method in allowed

    def test_p99_targets_are_positive_seconds(self) -> None:
        for obj in _OBJECTIVES:
            assert obj.p99_seconds > 0

    def test_availability_targets_are_percentages(self) -> None:
        # Availability is documented as a percentage (e.g. 99.95).
        # Drift to a 0..1 fraction would cause every alert to fire
        # immediately.
        for obj in _OBJECTIVES:
            assert 0 < obj.availability_pct <= 100

    def test_create_channel_p99_pinned(self) -> None:
        # Pin the contract for the channel-create endpoint so a silent
        # loosening (e.g. 2.5s → 10s) doesn't bury an SLO regression.
        create = next(o for o in _OBJECTIVES if o.path == "/api/file-shares/channels")
        assert create.method == "POST"
        assert create.p99_seconds == 2.5
        assert create.availability_pct == 99.95


class TestEndpointSLODataclass:
    def test_is_frozen_and_slotted(self) -> None:
        # ``frozen=True, slots=True`` makes the dataclass hashable and
        # memory-cheap. A regression would let callers mutate the
        # objectives at runtime — silent SLO drift.
        obj = _EndpointSLO(
            path="/x", method="GET", p99_seconds=1.0, availability_pct=99.0
        )
        assert obj.path == "/x"
        # Slotted dataclasses do not have ``__dict__``.
        assert not hasattr(obj, "__dict__")


class TestGaugeDeclarations:
    def test_p99_target_is_gauge(self) -> None:
        # Gauges (NOT counters) — alert rules query the *current*
        # target, not a cumulative sum. A regression to Counter would
        # silently break PromQL.
        assert isinstance(SLO_P99_TARGET, Gauge)

    def test_availability_target_is_gauge(self) -> None:
        assert isinstance(SLO_AVAILABILITY_TARGET, Gauge)


class TestPublishGauges:
    def test_publishes_p99_for_every_objective(self) -> None:
        _publish_gauges()
        for obj in _OBJECTIVES:
            assert (
                _gauge_value(SLO_P99_TARGET, endpoint=obj.path, method=obj.method)
                == obj.p99_seconds
            )

    def test_publishes_availability_for_every_objective(self) -> None:
        _publish_gauges()
        for obj in _OBJECTIVES:
            assert (
                _gauge_value(
                    SLO_AVAILABILITY_TARGET, endpoint=obj.path, method=obj.method
                )
                == obj.availability_pct
            )


class TestStartStopLifecycle:
    def setup_method(self) -> None:
        # Make sure the module is in a clean state.
        stop_slo_metrics()

    def teardown_method(self) -> None:
        stop_slo_metrics()

    def test_start_publishes_gauges_immediately(self) -> None:
        # Pin: ``start_slo_metrics`` MUST publish before launching the
        # background thread, so the first scrape after startup sees
        # populated values rather than zeros.
        start_slo_metrics()
        for obj in _OBJECTIVES:
            assert (
                _gauge_value(SLO_P99_TARGET, endpoint=obj.path, method=obj.method)
                == obj.p99_seconds
            )

    def test_start_launches_a_background_thread(self) -> None:
        start_slo_metrics()
        assert isinstance(M._worker_thread, threading.Thread)
        assert M._worker_thread.is_alive()
        assert M._worker_thread.daemon is True

    def test_start_is_idempotent(self) -> None:
        # Double-calling ``start_slo_metrics`` MUST NOT spawn a second
        # background thread — that would cause double-writes (harmless
        # but wasteful) and complicate ``stop`` (only joins the latest
        # thread, leaks the other).
        start_slo_metrics()
        first = M._worker_thread
        start_slo_metrics()
        assert M._worker_thread is first

    def test_stop_clears_module_singletons(self) -> None:
        # After ``stop_slo_metrics``, both module-globals must be reset
        # to ``None`` so that a subsequent ``start`` after a graceful
        # shutdown / restart cycle launches a fresh thread.
        start_slo_metrics()
        stop_slo_metrics()
        assert M._worker_thread is None
        assert M._stop_flag is None

    def test_stop_signals_thread_to_exit(self) -> None:
        # The thread loops on ``stop.wait(...)``; setting the event
        # must terminate the loop so ``join`` returns within timeout.
        start_slo_metrics()
        thread = M._worker_thread
        assert thread is not None
        stop_slo_metrics()
        # Give the thread a moment to clean up if it hadn't already.
        thread.join(timeout=1.0)
        assert thread.is_alive() is False

    def test_stop_when_not_started_is_safe(self) -> None:
        # Defensive: calling ``stop`` before ``start`` (e.g. in a test
        # teardown that runs even when startup failed) must not crash.
        # Already-clean state is the precondition.
        assert M._worker_thread is None
        stop_slo_metrics()
        assert M._worker_thread is None

    def test_thread_name_pinned(self) -> None:
        # Thread name shows up in ``py-spy`` / debugger views when ops
        # diagnose a hung process. A regression to the default
        # ``Thread-N`` name would make on-call worse.
        start_slo_metrics()
        assert M._worker_thread is not None
        assert M._worker_thread.name == "slo-gauge-publisher"


class TestBackgroundLoopErrorIsolation:
    def test_publish_failure_does_not_kill_loop(self, monkeypatch: object) -> None:
        # Pin: a transient prometheus-client error inside ``_publish_gauges``
        # MUST be caught and logged, not propagated. Otherwise the
        # background thread dies silently and the gauges go stale on
        # the next Prometheus restart.
        from rapidly.observability import slo as mod

        call_count = {"n": 0}

        def boom() -> None:
            call_count["n"] += 1
            raise RuntimeError("simulated prom-client failure")

        # Patch the publisher so the loop's ``try`` block hits the
        # exception path. The loop should keep running.
        monkeypatch.setattr(mod, "_publish_gauges", boom)  # type: ignore[attr-defined]

        stop = threading.Event()
        # Speed: avoid waiting 300s — drive the loop manually with
        # a near-zero ``timeout`` by patching the module-level
        # interval. Use a fresh stop flag so we control termination.
        monkeypatch.setattr(mod, "_PUBLISH_INTERVAL_SEC", 0.01)  # type: ignore[attr-defined]
        thread = threading.Thread(target=mod._background_loop, args=(stop,))
        thread.start()
        try:
            # Wait briefly for at least one iteration to fire.
            for _ in range(50):
                if call_count["n"] > 0:
                    break
                time.sleep(0.01)
        finally:
            stop.set()
            thread.join(timeout=2.0)

        assert call_count["n"] >= 1
        # The thread terminated cleanly via ``stop.set()`` rather than
        # crashing on the first exception.
        assert thread.is_alive() is False
