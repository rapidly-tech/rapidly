"""Tests for ``rapidly/analytics/metrics/types.py``.

Pins the dynamic Pydantic models generated from the ``METRICS``
registry + the response envelope + the per-interval limit schema used
by ``GET /metrics/limits``. These are the wire shapes the dashboard
keys on; silent schema drift breaks chart rendering.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from rapidly.analytics.metrics.metrics import METRICS, MetricType
from rapidly.analytics.metrics.types import (
    Metric,
    Metrics,
    MetricsIntervalLimit,
    MetricsIntervalsLimits,
    MetricsLimits,
    MetricsPeriod,
    MetricsResponse,
    MetricsTotals,
)


class TestMetricDescriptor:
    def test_roundtrips_through_pydantic(self) -> None:
        m = Metric(
            slug="file_share_sessions",
            display_name="File Share Sessions",
            type=MetricType.scalar,
        )
        assert m.slug == "file_share_sessions"
        assert m.display_name == "File Share Sessions"
        assert m.type == MetricType.scalar

    def test_accepts_all_MetricType_enum_values(self) -> None:
        for mt in MetricType:
            m = Metric(slug="x", display_name="X", type=mt)
            assert m.type == mt


class TestMetricsPeriod:
    def test_requires_timestamp(self) -> None:
        # ``timestamp`` is the one mandatory field; the dynamic per-
        # metric value fields are all Optional[int|float].
        period = MetricsPeriod(timestamp=datetime(2026, 4, 23, tzinfo=UTC))
        assert period.timestamp.tzinfo is not None

    def test_exposes_a_field_for_every_registered_metric(self) -> None:
        # Dynamic model generation: every entry in METRICS must
        # appear as an attribute on the MetricsPeriod model. Drift
        # catch for a new metric added without updating the types.
        period = MetricsPeriod(timestamp=datetime(2026, 4, 23, tzinfo=UTC))
        fields = MetricsPeriod.model_fields
        for m in METRICS:
            assert m.slug in fields, f"MetricsPeriod missing field for {m.slug}"
        # Default None so unpopulated metrics serialise cleanly.
        for m in METRICS:
            assert getattr(period, m.slug) is None


class TestMetricsTotals:
    def test_exposes_a_field_for_every_registered_metric(self) -> None:
        totals = MetricsTotals()
        for m in METRICS:
            assert m.slug in MetricsTotals.model_fields
            assert getattr(totals, m.slug) is None

    def test_accepts_int_and_float_values(self) -> None:
        # The field type is ``int | float | None`` — both scalar and
        # currency metrics route through the same schema.
        if METRICS:
            slug = METRICS[0].slug
            t = MetricsTotals(**{slug: 42})
            assert getattr(t, slug) == 42
            t = MetricsTotals(**{slug: 3.14})
            assert getattr(t, slug) == 3.14


class TestMetricsResponse:
    def test_requires_periods_totals_and_metrics(self) -> None:
        # The envelope for GET /metrics — the dashboard keys on these
        # three top-level fields.
        resp = MetricsResponse(
            periods=[MetricsPeriod(timestamp=datetime(2026, 4, 23, tzinfo=UTC))],
            totals=MetricsTotals(),
            metrics=Metrics(),
        )
        assert len(resp.periods) == 1
        assert isinstance(resp.totals, MetricsTotals)
        assert isinstance(resp.metrics, Metrics)


class TestMetricsIntervalLimit:
    def test_roundtrips_min_days_and_max_days(self) -> None:
        limit = MetricsIntervalLimit(min_days=0, max_days=7)
        assert limit.min_days == 0
        assert limit.max_days == 7


class TestMetricsIntervalsLimits:
    def test_requires_all_five_interval_limits(self) -> None:
        # MetricsIntervalsLimits must name every TimeInterval the
        # analytics endpoint supports; a missing field would 500 the
        # /metrics/limits response.
        limits = MetricsIntervalsLimits(
            hour=MetricsIntervalLimit(min_days=0, max_days=7),
            day=MetricsIntervalLimit(min_days=0, max_days=366),
            week=MetricsIntervalLimit(min_days=14, max_days=7 * 53),
            month=MetricsIntervalLimit(min_days=60, max_days=365 * 4),
            year=MetricsIntervalLimit(min_days=366, max_days=365 * 10),
        )
        for attr in ("hour", "day", "week", "month", "year"):
            assert isinstance(getattr(limits, attr), MetricsIntervalLimit)


class TestMetricsLimits:
    def test_envelope_pairs_min_date_with_per_interval_limits(self) -> None:
        payload = MetricsLimits(
            min_date=date(2024, 6, 1),
            intervals=MetricsIntervalsLimits(
                hour=MetricsIntervalLimit(min_days=0, max_days=7),
                day=MetricsIntervalLimit(min_days=0, max_days=366),
                week=MetricsIntervalLimit(min_days=14, max_days=7 * 53),
                month=MetricsIntervalLimit(min_days=60, max_days=365 * 4),
                year=MetricsIntervalLimit(min_days=366, max_days=365 * 10),
            ),
        )
        assert payload.min_date == date(2024, 6, 1)
        assert isinstance(payload.intervals, MetricsIntervalsLimits)
