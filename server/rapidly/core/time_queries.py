"""Time-interval helpers for analytics aggregation queries.

``TimeInterval`` enumerates the supported granularities (hour through
year) and provides convenience methods to build SQL interval literals
and ``date_trunc`` calls.

``is_under_limits`` validates that a requested date range does not
exceed the maximum allowed data-point count for the chosen interval.
"""

from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    CTE,
    Function,
    SQLColumnExpression,
    TextClause,
    cte,
    func,
    select,
    text,
)


class TimeInterval(StrEnum):
    """Supported aggregation granularities, ordered coarsest-first."""

    year = "year"
    month = "month"
    week = "week"
    day = "day"
    hour = "hour"

    def sql_interval(self) -> TextClause:
        """Return a ``'1 <unit>'::interval`` text clause."""
        return text(f"'1 {self.value}'::interval")

    def sql_date_trunc(
        self, column: SQLColumnExpression[datetime] | datetime
    ) -> Function[datetime]:
        """Wrap *column* in ``date_trunc('<unit>', column)``."""
        return func.date_trunc(self.value, column)


# ---------------------------------------------------------------------------
# Timestamp series CTE (for filling gaps in aggregation results)
# ---------------------------------------------------------------------------


def get_timestamp_series_cte(
    start_timestamp: datetime, end_timestamp: datetime, interval: TimeInterval
) -> CTE:
    """Generate a CTE with a continuous timestamp series at *interval* steps."""
    return cte(
        select(
            func.generate_series(
                start_timestamp, end_timestamp, interval.sql_interval()
            ).column_valued("timestamp")
        )
    )


# ---------------------------------------------------------------------------
# Range boundaries and validation
# ---------------------------------------------------------------------------

# Rapidly launched in late 2024; no meaningful data exists before this date.
MIN_DATETIME = datetime(2024, 6, 1)
MIN_DATE: date = MIN_DATETIME.date()

# Upper bound on the number of calendar days each interval is allowed to span.
MAX_INTERVAL_DAYS: dict[TimeInterval, int] = {
    TimeInterval.hour: 7,
    TimeInterval.day: 366,
    TimeInterval.week: 7 * 53,
    TimeInterval.month: 365 * 4,
    TimeInterval.year: 365 * 10,
}

# Lower bound: intervals finer than the minimum span produce misleading charts.
MIN_INTERVAL_DAYS: dict[TimeInterval, int] = {
    TimeInterval.hour: 0,
    TimeInterval.day: 0,
    TimeInterval.week: 14,
    TimeInterval.month: 60,
    TimeInterval.year: 366,
}


def is_under_limits(start_date: date, end_date: date, interval: TimeInterval) -> bool:
    """Return ``True`` when the date span fits within *interval*'s cap."""
    span = end_date.toordinal() - start_date.toordinal()
    return span <= MAX_INTERVAL_DAYS[interval]
