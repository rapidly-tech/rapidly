"""Metric response envelopes and dynamic per-metric data-point models.

Dynamically generates ``Metrics``, ``MetricsPeriod``, and ``MetricsTotals``
Pydantic models from the ``METRICS`` registry so that each registered metric
appears as an optional field.  Also defines the ``MetricsResponse`` wrapper
and the interval-limit configuration used by the ``/metrics/limits`` endpoint.
"""

from datetime import date
from typing import TYPE_CHECKING

from pydantic import AwareDatetime, Field, create_model

from rapidly.core.types import Schema

from .metrics import METRICS, MetricType

# ---------------------------------------------------------------------------
# Metric descriptor
# ---------------------------------------------------------------------------


class Metric(Schema):
    """Information about a metric."""

    slug: str = Field(description="Unique identifier for the metric.")
    display_name: str = Field(description="Human-readable name for the metric.")
    type: MetricType = Field(
        description=(
            "Type of the metric, useful to know the unit or format of the value."
        )
    )


# ---------------------------------------------------------------------------
# Dynamic per-metric models  (generated from the METRICS registry)
# ---------------------------------------------------------------------------

_metric_fields = {m.slug: (Metric | None, None) for m in METRICS}
_value_fields = {m.slug: (int | float | None, None) for m in METRICS}

if TYPE_CHECKING:

    class Metrics(Schema):
        def __getattr__(self, name: str) -> Metric | None: ...

    class MetricsPeriod(Schema):
        timestamp: AwareDatetime

        def __getattr__(self, name: str) -> int | float | None: ...

    class MetricsTotals(Schema):
        def __getattr__(self, name: str) -> int | float | None: ...

else:
    Metrics = create_model(
        "Metrics",
        __base__=Schema,
        **_metric_fields,
    )

    class _PeriodBase(Schema):
        """Single time-bucket with a value per active metric."""

        timestamp: AwareDatetime = Field(description="Timestamp of this period data.")

    MetricsPeriod = create_model(
        "MetricPeriod",
        __base__=_PeriodBase,
        **_value_fields,
    )

    class _TotalsBase(Schema):
        """Aggregated metric values over the entire selected date range.

        The aggregation strategy depends on the individual metric type
        (e.g. sum for counts, latest for gauge values).
        """

    MetricsTotals = create_model(
        "MetricsTotals",
        __base__=_TotalsBase,
        **_value_fields,
    )


# ---------------------------------------------------------------------------
# Response envelope
# ---------------------------------------------------------------------------


class MetricsResponse(Schema):
    """Top-level response for the ``GET /metrics`` endpoint."""

    periods: list[MetricsPeriod] = Field(description="List of data for each timestamp.")
    totals: MetricsTotals = Field(description="Totals for the whole selected period.")
    metrics: Metrics = Field(description="Information about the returned metrics.")


# ---------------------------------------------------------------------------
# Interval-limit configuration
# ---------------------------------------------------------------------------


class MetricsIntervalLimit(Schema):
    """Allowed day-range for a single time interval."""

    min_days: int = Field(description="Minimum number of days for this interval.")
    max_days: int = Field(description="Maximum number of days for this interval.")


class MetricsIntervalsLimits(Schema):
    """Per-interval day-range constraints."""

    hour: MetricsIntervalLimit = Field(description="Limits for the hour interval.")
    day: MetricsIntervalLimit = Field(description="Limits for the day interval.")
    week: MetricsIntervalLimit = Field(description="Limits for the week interval.")
    month: MetricsIntervalLimit = Field(description="Limits for the month interval.")
    year: MetricsIntervalLimit = Field(description="Limits for the year interval.")


class MetricsLimits(Schema):
    """Overall date constraints returned by ``GET /metrics/limits``."""

    min_date: date = Field(description="Minimum date to get metrics.")
    intervals: MetricsIntervalsLimits = Field(description="Limits for each interval.")
