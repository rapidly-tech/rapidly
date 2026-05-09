"""Tests for ``rapidly/observability/otel_prometheus.py``.

OTel-to-prometheus_client bridge for multiprocess metric export.
Five load-bearing surfaces:

- Label arity & names — ``_LABEL_NAMES = ["service", "state"]``;
  Grafana panels query exactly these labels and the worker pool
  dashboard joins via ``service`` (set from OTel ``pool.name``).
  Drift here means the dashboard goes blank.
- Fallback label string ``"unknown"`` — Prometheus rejects empty
  label values, so a regression that emitted ``""`` instead of
  ``"unknown"`` would crash the metric write path silently.
- Dotted-OTel-name → underscored-Prom-name conversion — Prometheus
  REJECTS dot-containing names, so this transformation is mandatory.
- ``multiprocess_mode="livesum"`` on the underlying Gauge — the
  workers fork lightweight health servers and the values across
  processes must be SUMMED (not last-write-wins) to be correct.
- Unsupported instrument kinds (Counter, Histogram, Gauge,
  ObservableCounter, ObservableUpDownCounter, ObservableGauge)
  must raise NotImplementedError loudly — silent fallback to a
  no-op would let new instrumentation calls disappear from
  dashboards without warning.
"""

from __future__ import annotations

import pytest

from rapidly.observability.otel_prometheus import (
    _FALLBACK_LABEL,
    _LABEL_NAMES,
    PrometheusMeter,
    PrometheusMeterProvider,
    PrometheusUpDownCounter,
    _labels_from_attributes,
    _meter_cache_key,
    _otel_name_to_prom,
)


class TestLabelConstants:
    def test_label_names_pinned(self) -> None:
        # Grafana panels and the worker-pool dashboard query exactly
        # these labels. Adding/removing one is a breaking change for
        # PromQL queries.
        assert _LABEL_NAMES == ["service", "state"]

    def test_fallback_label_is_unknown_string(self) -> None:
        # Prometheus rejects empty-string label values. Pin the
        # fallback to ``"unknown"`` — drift to ``""`` would crash
        # the metric write path silently.
        assert _FALLBACK_LABEL == "unknown"
        assert _FALLBACK_LABEL != ""


class TestLabelsFromAttributes:
    def test_none_attrs_uses_fallback_for_both_labels(self) -> None:
        # Pin: passing ``None`` (the default) yields fallback for both
        # labels, NOT a KeyError or empty dict.
        labels = _labels_from_attributes(None)
        assert labels == {"service": "unknown", "state": "unknown"}

    def test_empty_attrs_uses_fallback_for_both_labels(self) -> None:
        # ``not attrs`` short-circuit — empty dict is truthy-False in
        # the bridge's check.
        labels = _labels_from_attributes({})
        assert labels == {"service": "unknown", "state": "unknown"}

    def test_pool_name_maps_to_service_label(self) -> None:
        # The OTel attribute ``pool.name`` (dotted) is the connection-
        # pool identifier emitted by SQLAlchemy / httpx instrumentation.
        # The bridge maps it to the Prometheus label ``service``.
        labels = _labels_from_attributes({"pool.name": "default"})
        assert labels["service"] == "default"
        assert labels["state"] == "unknown"

    def test_state_maps_to_state_label(self) -> None:
        labels = _labels_from_attributes({"state": "checked_out"})
        assert labels["state"] == "checked_out"
        assert labels["service"] == "unknown"

    def test_both_attributes_present(self) -> None:
        labels = _labels_from_attributes({"pool.name": "read_replica", "state": "idle"})
        assert labels == {"service": "read_replica", "state": "idle"}

    def test_unknown_attributes_are_ignored(self) -> None:
        # Pin: only ``pool.name`` and ``state`` are read. A regression
        # that picked up arbitrary keys would explode the cardinality
        # budget on noisy attributes.
        labels = _labels_from_attributes(
            {"pool.name": "p", "state": "s", "noise": "ignore-me"}
        )
        assert labels == {"service": "p", "state": "s"}

    def test_non_string_attribute_value_is_stringified(self) -> None:
        # Pin: integer / bool values get ``str()``-ified rather than
        # passed through (Prometheus labels are strings only).
        labels = _labels_from_attributes({"pool.name": 42, "state": True})
        assert labels == {"service": "42", "state": "True"}


class TestOtelNameToProm:
    def test_dots_become_underscores(self) -> None:
        # Prometheus REJECTS dot-containing names. Pin the conversion.
        assert _otel_name_to_prom("db.connection.pool") == "db_connection_pool"

    def test_no_dots_passthrough(self) -> None:
        assert _otel_name_to_prom("already_safe") == "already_safe"

    def test_empty_string(self) -> None:
        # Defensive: empty input doesn't crash. Edge case for
        # malformed instrumentation.
        assert _otel_name_to_prom("") == ""


class TestPrometheusUpDownCounter:
    def test_add_increments_underlying_gauge(self) -> None:
        # End-to-end: ``add(amount, attrs)`` must reach the Prometheus
        # gauge with the correct labels. A regression that mis-routed
        # the labels would make every observation land on the
        # fallback ``unknown`` series.
        counter = PrometheusUpDownCounter(
            name="test.bridge.counter.increment", unit="", description="d"
        )
        counter.add(3, attributes={"pool.name": "primary", "state": "active"})
        sample = counter._gauge.labels(service="primary", state="active")._value.get()
        assert sample == 3

    def test_add_supports_negative_amounts(self) -> None:
        # UpDownCounter (NOT plain Counter) — negative ``add`` is the
        # contract. A regression to a plain ``inc()`` that rejected
        # negatives would break pool-checkout/checkin tracking.
        counter = PrometheusUpDownCounter(
            name="test.bridge.counter.negative", unit="", description="d"
        )
        counter.add(5, attributes={"pool.name": "p", "state": "s"})
        counter.add(-2, attributes={"pool.name": "p", "state": "s"})
        sample = counter._gauge.labels(service="p", state="s")._value.get()
        assert sample == 3

    def test_add_with_none_attributes_uses_fallback_labels(self) -> None:
        # Pin: ``attributes=None`` routes to ``unknown`` series rather
        # than crashing on a missing key.
        counter = PrometheusUpDownCounter(
            name="test.bridge.counter.none_attrs", unit="", description="d"
        )
        counter.add(1)
        sample = counter._gauge.labels(service="unknown", state="unknown")._value.get()
        assert sample == 1


class TestPrometheusMeter:
    def test_create_up_down_counter_returns_supported_instrument(self) -> None:
        meter = PrometheusMeter("m", None, None)
        instr = meter.create_up_down_counter("test.meter.created")
        assert isinstance(instr, PrometheusUpDownCounter)

    def test_create_up_down_counter_is_idempotent(self) -> None:
        # Pin: repeated ``create_up_down_counter(name)`` returns the
        # SAME instrument. Otherwise creating the same Prom Gauge twice
        # would raise (duplicated timeseries) and the worker would
        # fail to boot.
        meter = PrometheusMeter("m", None, None)
        first = meter.create_up_down_counter("test.meter.idempotent")
        second = meter.create_up_down_counter("test.meter.idempotent")
        assert first is second

    @pytest.mark.parametrize(
        "factory_name",
        [
            "create_counter",
            "create_histogram",
            "create_gauge",
            "create_observable_counter",
            "create_observable_up_down_counter",
            "create_observable_gauge",
        ],
    )
    def test_unsupported_instruments_raise_not_implemented(
        self, factory_name: str
    ) -> None:
        # Pin: unsupported instrument kinds raise loudly. A regression
        # that returned a no-op stub would let new instrumentation calls
        # disappear from dashboards without warning.
        meter = PrometheusMeter("m", None, None)
        factory = getattr(meter, factory_name)
        with pytest.raises(NotImplementedError, match="not supported"):
            factory("anything")

    def test_meter_props_preserved(self) -> None:
        meter = PrometheusMeter("svc.name", "1.2.3", "https://example/schema")
        assert meter.name == "svc.name"
        assert meter.version == "1.2.3"
        assert meter.schema_url == "https://example/schema"


class TestMeterCacheKey:
    def test_combines_all_three_inputs(self) -> None:
        # Pin: cache key includes name + version + schema_url so two
        # different versions of the same meter don't collide.
        a = _meter_cache_key("foo", "1.0", "https://x")
        b = _meter_cache_key("foo", "2.0", "https://x")
        assert a != b

    def test_handles_none_components(self) -> None:
        # Defensive: callers commonly pass ``None`` for version and/or
        # schema_url. Pin the format so a None doesn't crash.
        key = _meter_cache_key("foo", None, None)
        assert key == "foo:None:None"


class TestPrometheusMeterProvider:
    def test_get_meter_returns_prometheus_meter(self) -> None:
        provider = PrometheusMeterProvider()
        meter = provider.get_meter("svc")
        assert isinstance(meter, PrometheusMeter)

    def test_get_meter_caches_by_name_version_schema(self) -> None:
        # Pin: same (name, version, schema_url) returns the SAME
        # meter instance. Otherwise instruments registered through
        # one meter would be invisible to subsequent ``get_meter``
        # callers.
        provider = PrometheusMeterProvider()
        a = provider.get_meter("svc", "1.0", "https://x")
        b = provider.get_meter("svc", "1.0", "https://x")
        assert a is b

    def test_different_versions_yield_distinct_meters(self) -> None:
        # Pin: version drift correctly yields a fresh meter. Otherwise
        # a v2 instrument with an incompatible name would conflict
        # with the v1 cache entry.
        provider = PrometheusMeterProvider()
        a = provider.get_meter("svc", "1.0", "https://x")
        b = provider.get_meter("svc", "2.0", "https://x")
        assert a is not b
