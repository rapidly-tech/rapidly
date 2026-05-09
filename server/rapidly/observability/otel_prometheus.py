"""Bridges OpenTelemetry metrics to prometheus_client for multiprocess export.

Implements a minimal OTel MeterProvider backed by prometheus_client Gauges,
supporting multiprocess mode via PROMETHEUS_MULTIPROC_DIR.
"""

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from opentelemetry.metrics import (
    CallbackT,
    Counter,
    Histogram,
    Meter,
    MeterProvider,
    ObservableCounter,
    ObservableGauge,
    ObservableUpDownCounter,
    UpDownCounter,
)
from opentelemetry.metrics import _Gauge as Gauge
from prometheus_client import Gauge as PromGauge

import rapidly.observability.metrics  # noqa: F401  # Sets PROMETHEUS_MULTIPROC_DIR

if TYPE_CHECKING:
    from opentelemetry.context import Context

# Attribute values that OTel allows on metric data points.
type _AttrValue = (
    str
    | bool
    | int
    | float
    | Sequence[str]
    | Sequence[bool]
    | Sequence[int]
    | Sequence[float]
)
type Attributes = Mapping[str, _AttrValue] | None

_FALLBACK_LABEL = "unknown"
_LABEL_NAMES: list[str] = ["service", "state"]


def _labels_from_attributes(attrs: Attributes) -> dict[str, str]:
    """Extract Prometheus label values from OTel attributes."""
    if not attrs:
        return {k: _FALLBACK_LABEL for k in _LABEL_NAMES}
    return {
        "service": str(attrs.get("pool.name", _FALLBACK_LABEL)),
        "state": str(attrs.get("state", _FALLBACK_LABEL)),
    }


def _otel_name_to_prom(name: str) -> str:
    """Convert dotted OTel metric name to underscored Prometheus name."""
    return name.replace(".", "_")


# ---------------------------------------------------------------------------
# Instrument wrappers
# ---------------------------------------------------------------------------


class PrometheusUpDownCounter(UpDownCounter):
    def __init__(self, name: str, unit: str, description: str) -> None:
        self._gauge = PromGauge(
            _otel_name_to_prom(name),
            description,
            _LABEL_NAMES,
            multiprocess_mode="livesum",
        )

    def add(
        self,
        amount: int | float,
        attributes: Attributes = None,
        context: "Context | None" = None,
    ) -> None:
        self._gauge.labels(**_labels_from_attributes(attributes)).inc(amount)


def _not_supported(kind: str) -> NotImplementedError:
    return NotImplementedError(f"{kind} is not supported by the Prometheus bridge")


# ---------------------------------------------------------------------------
# Meter & provider
# ---------------------------------------------------------------------------


class PrometheusMeter(Meter):
    """A thin Meter that only materialises UpDownCounter instruments."""

    def __init__(self, meter_name: str, ver: str | None, url: str | None) -> None:
        self._meter_name = meter_name
        self._ver = ver
        self._url = url
        self._registry: dict[str, Any] = {}

    # -- required read-only props --
    @property
    def name(self) -> str:
        return self._meter_name

    @property
    def version(self) -> str | None:
        return self._ver

    @property
    def schema_url(self) -> str | None:
        return self._url

    # -- instrument factories --
    def create_up_down_counter(
        self, name: str, unit: str = "", description: str = ""
    ) -> UpDownCounter:
        if name not in self._registry:
            self._registry[name] = PrometheusUpDownCounter(name, unit, description)
        return self._registry[name]

    def create_counter(
        self, name: str, unit: str = "", description: str = ""
    ) -> Counter:
        raise _not_supported("Counter")

    def create_histogram(
        self,
        name: str,
        unit: str = "",
        description: str = "",
        *,
        explicit_bucket_boundaries_advisory: Sequence[float] | None = None,
    ) -> Histogram:
        raise _not_supported("Histogram")

    def create_gauge(self, name: str, unit: str = "", description: str = "") -> Gauge:
        raise _not_supported("Gauge")

    def create_observable_counter(
        self,
        name: str,
        callbacks: Sequence[CallbackT] | None = None,
        unit: str = "",
        description: str = "",
    ) -> ObservableCounter:
        raise _not_supported("ObservableCounter")

    def create_observable_up_down_counter(
        self,
        name: str,
        callbacks: Sequence[CallbackT] | None = None,
        unit: str = "",
        description: str = "",
    ) -> ObservableUpDownCounter:
        raise _not_supported("ObservableUpDownCounter")

    def create_observable_gauge(
        self,
        name: str,
        callbacks: Sequence[CallbackT] | None = None,
        unit: str = "",
        description: str = "",
    ) -> ObservableGauge:
        raise _not_supported("ObservableGauge")


def _meter_cache_key(name: str, version: str | None, schema_url: str | None) -> str:
    return f"{name}:{version}:{schema_url}"


class PrometheusMeterProvider(MeterProvider):
    def __init__(self) -> None:
        self._meters: dict[str, PrometheusMeter] = {}

    def get_meter(
        self,
        name: str,
        version: str | None = None,
        schema_url: str | None = None,
        attributes: Attributes = None,
    ) -> Meter:
        cache_key = _meter_cache_key(name, version, schema_url)
        if cache_key not in self._meters:
            self._meters[cache_key] = PrometheusMeter(name, version, schema_url)
        return self._meters[cache_key]
