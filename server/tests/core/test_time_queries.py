"""Tests for ``rapidly/core/time_queries.py`` — time-interval helpers
for the analytics aggregation pipeline.

Pins:
- ``TimeInterval`` enum membership + coarsest-to-finest ordering
- ``sql_interval`` emits the documented ``'1 <unit>'::interval`` form
- ``sql_date_trunc`` wraps the column in ``date_trunc('<unit>', col)``
- ``MIN_DATETIME`` / ``MIN_DATE`` invariant (platform's earliest data)
- ``is_under_limits`` clamps span × interval combinations per the
  documented MAX_INTERVAL_DAYS cap
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import Column, DateTime
from sqlalchemy.dialects import postgresql

from rapidly.core.time_queries import (
    MAX_INTERVAL_DAYS,
    MIN_DATE,
    MIN_DATETIME,
    MIN_INTERVAL_DAYS,
    TimeInterval,
    is_under_limits,
)


def _sql(clause: Any) -> str:
    """Compile an expression against the PostgreSQL dialect, with
    literal binds so numeric / string values render inline."""
    return str(
        clause.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


class TestTimeIntervalMembership:
    def test_contains_the_five_documented_granularities(self) -> None:
        assert {i.value for i in TimeInterval} == {
            "year",
            "month",
            "week",
            "day",
            "hour",
        }

    def test_ordered_coarsest_first(self) -> None:
        # The docstring pins "ordered coarsest-first". Iteration order
        # on StrEnum matches declaration order.
        assert list(TimeInterval) == [
            TimeInterval.year,
            TimeInterval.month,
            TimeInterval.week,
            TimeInterval.day,
            TimeInterval.hour,
        ]


class TestSqlInterval:
    def test_emits_the_documented_1_unit_interval_text_clause(self) -> None:
        # Each interval compiles to ``'1 <unit>'::interval``.
        assert _sql(TimeInterval.day.sql_interval()) == "'1 day'::interval"
        assert _sql(TimeInterval.hour.sql_interval()) == "'1 hour'::interval"
        assert _sql(TimeInterval.year.sql_interval()) == "'1 year'::interval"


class TestSqlDateTrunc:
    def test_wraps_the_column_in_date_trunc(self) -> None:
        col = Column("created_at", DateTime)
        out = _sql(TimeInterval.day.sql_date_trunc(col))
        # Postgres compilation — matches date_trunc('day', created_at).
        assert "date_trunc" in out
        assert "'day'" in out
        assert "created_at" in out

    def test_uses_the_correct_unit_per_interval(self) -> None:
        col = Column("ts", DateTime)
        for interval, unit in [
            (TimeInterval.hour, "'hour'"),
            (TimeInterval.week, "'week'"),
            (TimeInterval.month, "'month'"),
            (TimeInterval.year, "'year'"),
        ]:
            out = _sql(interval.sql_date_trunc(col))
            assert unit in out, f"{interval} expected {unit} in {out}"


class TestMinDatetime:
    def test_is_a_naive_datetime(self) -> None:
        # The module imports the symbol without tz; pinning the shape
        # prevents an accidental ``datetime(..., tzinfo=UTC)`` switch
        # that'd require a schema migration for every time column.
        assert MIN_DATETIME.tzinfo is None

    def test_date_member_matches_datetime(self) -> None:
        assert MIN_DATE == MIN_DATETIME.date()

    def test_is_before_any_currently_valid_date(self) -> None:
        # Rapidly launched late 2024; any production data is after this.
        # Pinning the ordering catches a refactor that'd accidentally
        # move the baseline forward (breaking back-dated analytics).
        assert MIN_DATETIME < datetime(2025, 1, 1)


class TestMaxIntervalDays:
    def test_covers_every_TimeInterval(self) -> None:
        # Drift-catch: every interval must have a cap.
        assert set(MAX_INTERVAL_DAYS.keys()) == set(TimeInterval)

    def test_min_intervals_covers_every_TimeInterval(self) -> None:
        assert set(MIN_INTERVAL_DAYS.keys()) == set(TimeInterval)

    def test_caps_are_monotonic_coarser_larger(self) -> None:
        # hour < day < week < month < year. Otherwise the UX is weird
        # (asking for hour granularity allows MORE history than day).
        caps = [MAX_INTERVAL_DAYS[i] for i in TimeInterval]
        # TimeInterval iterates year → hour (coarsest first), so caps
        # should be DESCENDING when iterated.
        assert caps == sorted(caps, reverse=True)


class TestIsUnderLimits:
    def test_zero_day_span_is_under_every_limit(self) -> None:
        today = date(2026, 4, 23)
        for interval in TimeInterval:
            assert is_under_limits(today, today, interval) is True

    def test_day_span_exactly_at_cap_is_allowed(self) -> None:
        start = date(2026, 1, 1)
        end = start + timedelta(days=MAX_INTERVAL_DAYS[TimeInterval.day])
        assert is_under_limits(start, end, TimeInterval.day) is True

    def test_day_span_one_over_cap_is_rejected(self) -> None:
        start = date(2026, 1, 1)
        end = start + timedelta(days=MAX_INTERVAL_DAYS[TimeInterval.day] + 1)
        assert is_under_limits(start, end, TimeInterval.day) is False

    def test_hour_cap_is_one_week(self) -> None:
        start = date(2026, 1, 1)
        seven = start + timedelta(days=7)
        eight = start + timedelta(days=8)
        assert is_under_limits(start, seven, TimeInterval.hour) is True
        assert is_under_limits(start, eight, TimeInterval.hour) is False

    def test_year_cap_is_ten_years(self) -> None:
        start = date(2020, 1, 1)
        ten = start + timedelta(days=365 * 10)
        assert is_under_limits(start, ten, TimeInterval.year) is True
        too_long = start + timedelta(days=365 * 10 + 1)
        assert is_under_limits(start, too_long, TimeInterval.year) is False
