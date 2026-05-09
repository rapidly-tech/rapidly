"""Metric definitions and interval-aware accumulator framework.

Defines ``Metric`` protocol, concrete metric types (counts, revenue,
cumulative totals), and the ``MetricPeriod`` bucketing logic used by
the dashboard analytics endpoints.
"""

from collections import deque
from collections.abc import Iterable
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar, Protocol

if TYPE_CHECKING:
    from .types import MetricsPeriod

from sqlalchemy import (
    ColumnElement,
    Float,
    Integer,
    case,
    func,
    select,
    type_coerce,
)

from rapidly.core.time_queries import TimeInterval
from rapidly.models import (
    FileSharePayment,
    FileShareSession,
)
from rapidly.models.event import Event
from rapidly.models.file_share_payment import FileSharePaymentStatus
from rapidly.models.file_share_session import FileShareSessionStatus

from .queries import MetricQuery

# ── Metric Definitions ──


class MetricType(StrEnum):
    scalar = "scalar"
    currency = "currency"
    currency_sub_cent = "currency_sub_cent"
    percentage = "percentage"


def cumulative_sum(periods: Iterable["MetricsPeriod"], slug: str) -> int | float:
    return sum(getattr(p, slug) or 0 for p in periods)


def cumulative_last(periods: Iterable["MetricsPeriod"], slug: str) -> int | float:
    dd = deque((getattr(p, slug) for p in periods), maxlen=1)
    value = dd.pop()
    return value if value is not None else 0


class Metric(Protocol):
    slug: ClassVar[str]
    display_name: ClassVar[str]
    type: ClassVar[MetricType]

    @classmethod
    def get_cumulative(cls, periods: Iterable["MetricsPeriod"]) -> int | float: ...


class SQLMetric(Metric, Protocol):
    query: ClassVar[MetricQuery]

    @classmethod
    def get_sql_expression(
        cls, t: ColumnElement[datetime], i: TimeInterval, now: datetime
    ) -> ColumnElement[int] | ColumnElement[float]: ...


class MetaMetric(Metric, Protocol):
    @classmethod
    def compute_from_period(cls, period: "MetricsPeriod") -> int | float: ...


# ── SQL Metrics: Cost and User ──


class CostsMetric(SQLMetric):
    slug = "costs"
    display_name = "Costs"
    type = MetricType.currency_sub_cent
    query = MetricQuery.events

    @classmethod
    def get_sql_expression(
        cls, t: ColumnElement[datetime], i: TimeInterval, now: datetime
    ) -> ColumnElement[int]:
        return func.sum(
            Event.user_metadata["_cost"]["amount"].as_numeric(17, 12)
        ).filter(Event.user_metadata["_cost"].is_not(None))

    @classmethod
    def get_cumulative(cls, periods: Iterable["MetricsPeriod"]) -> int | float:
        return cumulative_sum(periods, cls.slug)


class CumulativeCostsMetric(SQLMetric):
    slug = "cumulative_costs"
    display_name = "Cumulative Costs"
    type = MetricType.currency_sub_cent
    query = MetricQuery.events

    get_sql_expression = CostsMetric.get_sql_expression

    @classmethod
    def get_cumulative(cls, periods: Iterable["MetricsPeriod"]) -> int | float:
        return cumulative_last(periods, cls.slug)


class CostPerUserMetric(SQLMetric):
    slug = "cost_per_user"
    display_name = "Cost Per User"
    type = MetricType.currency_sub_cent
    query = MetricQuery.events

    @classmethod
    def get_sql_expression(
        cls, t: ColumnElement[datetime], i: TimeInterval, now: datetime
    ) -> ColumnElement[float]:
        total_customers = func.count(func.distinct(Event.customer_id)) + func.count(
            func.distinct(Event.external_customer_id)
        )

        total_costs = func.sum(
            func.coalesce(Event.user_metadata["_cost"]["amount"].as_numeric(17, 12), 0)
        )

        return type_coerce(
            case(
                (total_customers == 0, 0),
                else_=total_costs / total_customers,
            ),
            Float,
        )

    @classmethod
    def get_cumulative(cls, periods: Iterable["MetricsPeriod"]) -> float:
        total_active_users = cumulative_last(periods, ActiveUserMetric.slug)
        total_costs = sum(getattr(p, CostsMetric.slug) or 0 for p in periods)
        return total_costs / total_active_users if total_active_users > 0 else 0.0


class ActiveUserMetric(SQLMetric):
    slug = "active_user_by_event"
    display_name = "Active User (By event)"
    type = MetricType.scalar
    query = MetricQuery.events

    @classmethod
    def get_sql_expression(
        cls, t: ColumnElement[datetime], i: TimeInterval, now: datetime
    ) -> ColumnElement[int]:
        return func.count(func.distinct(Event.customer_id)) + func.count(
            func.distinct(Event.external_customer_id)
        )

    @classmethod
    def get_cumulative(cls, periods: Iterable["MetricsPeriod"]) -> int:
        return int(cumulative_last(periods, cls.slug))


# ── SQL Metrics: File Share Sessions ──


class FileShareSessionsMetric(SQLMetric):
    slug = "file_share_sessions"
    display_name = "File Share Sessions"
    type = MetricType.scalar
    query = MetricQuery.file_share_sessions

    @classmethod
    def get_sql_expression(
        cls, t: ColumnElement[datetime], i: TimeInterval, now: datetime
    ) -> ColumnElement[int]:
        return func.count(FileShareSession.id)

    @classmethod
    def get_cumulative(cls, periods: Iterable["MetricsPeriod"]) -> int | float:
        return cumulative_sum(periods, cls.slug)


class FileShareDownloadsMetric(SQLMetric):
    slug = "file_share_downloads"
    display_name = "File Share Downloads"
    type = MetricType.scalar
    query = MetricQuery.file_share_sessions

    @classmethod
    def get_sql_expression(
        cls, t: ColumnElement[datetime], i: TimeInterval, now: datetime
    ) -> ColumnElement[int]:
        return func.coalesce(func.sum(FileShareSession.download_count), 0)

    @classmethod
    def get_cumulative(cls, periods: Iterable["MetricsPeriod"]) -> int | float:
        return cumulative_sum(periods, cls.slug)


class FileShareFreeSessionsMetric(SQLMetric):
    slug = "file_share_free_sessions"
    display_name = "Free File Shares"
    type = MetricType.scalar
    query = MetricQuery.file_share_sessions

    @classmethod
    def get_sql_expression(
        cls, t: ColumnElement[datetime], i: TimeInterval, now: datetime
    ) -> ColumnElement[int]:
        return func.count(FileShareSession.id).filter(
            FileShareSession.price_cents.is_(None)
        )

    @classmethod
    def get_cumulative(cls, periods: Iterable["MetricsPeriod"]) -> int | float:
        return cumulative_sum(periods, cls.slug)


class FileShareActiveSessionsMetric(SQLMetric):
    slug = "file_share_active_sessions"
    display_name = "Active Sessions"
    type = MetricType.scalar
    query = MetricQuery.file_share_sessions

    @classmethod
    def get_sql_expression(
        cls, t: ColumnElement[datetime], i: TimeInterval, now: datetime
    ) -> ColumnElement[int]:
        return func.count(FileShareSession.id).filter(
            FileShareSession.status == FileShareSessionStatus.active
        )

    @classmethod
    def get_cumulative(cls, periods: Iterable["MetricsPeriod"]) -> int | float:
        return cumulative_last(periods, cls.slug)


class FileShareCompletedSessionsMetric(SQLMetric):
    slug = "file_share_completed_sessions"
    display_name = "Completed Sessions"
    type = MetricType.scalar
    query = MetricQuery.file_share_sessions

    @classmethod
    def get_sql_expression(
        cls, t: ColumnElement[datetime], i: TimeInterval, now: datetime
    ) -> ColumnElement[int]:
        return func.count(FileShareSession.id).filter(
            FileShareSession.status == FileShareSessionStatus.completed
        )

    @classmethod
    def get_cumulative(cls, periods: Iterable["MetricsPeriod"]) -> int | float:
        return cumulative_sum(periods, cls.slug)


class FileShareExpiredSessionsMetric(SQLMetric):
    slug = "file_share_expired_sessions"
    display_name = "Expired Sessions"
    type = MetricType.scalar
    query = MetricQuery.file_share_sessions

    @classmethod
    def get_sql_expression(
        cls, t: ColumnElement[datetime], i: TimeInterval, now: datetime
    ) -> ColumnElement[int]:
        return func.count(FileShareSession.id).filter(
            FileShareSession.status == FileShareSessionStatus.expired
        )

    @classmethod
    def get_cumulative(cls, periods: Iterable["MetricsPeriod"]) -> int | float:
        return cumulative_sum(periods, cls.slug)


class FileShareAvgDownloadsMetric(SQLMetric):
    slug = "file_share_avg_downloads"
    display_name = "Avg Downloads Per Share"
    type = MetricType.scalar
    query = MetricQuery.file_share_sessions

    @classmethod
    def get_sql_expression(
        cls, t: ColumnElement[datetime], i: TimeInterval, now: datetime
    ) -> ColumnElement[float]:
        total_sessions = func.count(FileShareSession.id)
        total_downloads = func.coalesce(func.sum(FileShareSession.download_count), 0)
        return type_coerce(
            case(
                (total_sessions == 0, 0),
                else_=type_coerce(total_downloads, Float)
                / type_coerce(total_sessions, Float),
            ),
            Float,
        )

    @classmethod
    def get_cumulative(cls, periods: Iterable["MetricsPeriod"]) -> float:
        total_sessions = sum(getattr(p, "file_share_sessions") or 0 for p in periods)
        total_downloads = sum(getattr(p, "file_share_downloads") or 0 for p in periods)
        return total_downloads / total_sessions if total_sessions > 0 else 0.0


class FileShareTotalSizeBytesMetric(SQLMetric):
    slug = "file_share_total_size_bytes"
    display_name = "Total Data Shared (bytes)"
    type = MetricType.scalar
    query = MetricQuery.file_share_sessions

    @classmethod
    def get_sql_expression(
        cls, t: ColumnElement[datetime], i: TimeInterval, now: datetime
    ) -> ColumnElement[int]:
        return func.coalesce(func.sum(FileShareSession.file_size_bytes), 0)

    @classmethod
    def get_cumulative(cls, periods: Iterable["MetricsPeriod"]) -> int | float:
        return cumulative_sum(periods, cls.slug)


class CumulativeFileShareSessionsMetric(SQLMetric):
    slug = "cumulative_file_share_sessions"
    display_name = "Cumulative File Shares"
    type = MetricType.scalar
    query = MetricQuery.file_share_sessions

    get_sql_expression = FileShareSessionsMetric.get_sql_expression

    @classmethod
    def get_cumulative(cls, periods: Iterable["MetricsPeriod"]) -> int | float:
        return cumulative_last(periods, cls.slug)


class CumulativeFileShareDownloadsMetric(SQLMetric):
    slug = "cumulative_file_share_downloads"
    display_name = "Cumulative Downloads"
    type = MetricType.scalar
    query = MetricQuery.file_share_sessions

    get_sql_expression = FileShareDownloadsMetric.get_sql_expression

    @classmethod
    def get_cumulative(cls, periods: Iterable["MetricsPeriod"]) -> int | float:
        return cumulative_last(periods, cls.slug)


# ── SQL Metrics: File Share Revenue and Payments ──


class FileShareRevenueMetric(SQLMetric):
    slug = "file_share_revenue"
    display_name = "File Share Revenue"
    type = MetricType.currency
    query = MetricQuery.file_share_sessions

    @classmethod
    def get_sql_expression(
        cls, t: ColumnElement[datetime], i: TimeInterval, now: datetime
    ) -> ColumnElement[int]:
        payment_sum = (
            select(func.coalesce(func.sum(FileSharePayment.amount_cents), 0))
            .where(
                FileSharePayment.session_id == FileShareSession.id,
                FileSharePayment.status == FileSharePaymentStatus.completed,
            )
            .correlate(FileShareSession)
            .scalar_subquery()
        )
        return func.coalesce(func.sum(payment_sum), 0)

    @classmethod
    def get_cumulative(cls, periods: Iterable["MetricsPeriod"]) -> int | float:
        return cumulative_sum(periods, cls.slug)


class FileSharePaidSessionsMetric(SQLMetric):
    slug = "file_share_paid_sessions"
    display_name = "Paid File Shares"
    type = MetricType.scalar
    query = MetricQuery.file_share_sessions

    @classmethod
    def get_sql_expression(
        cls, t: ColumnElement[datetime], i: TimeInterval, now: datetime
    ) -> ColumnElement[int]:
        return func.count(FileShareSession.id).filter(
            FileShareSession.price_cents.is_not(None)
        )

    @classmethod
    def get_cumulative(cls, periods: Iterable["MetricsPeriod"]) -> int | float:
        return cumulative_sum(periods, cls.slug)


class FileShareAvgPriceMetric(SQLMetric):
    slug = "file_share_avg_price"
    display_name = "Average Share Price"
    type = MetricType.currency
    query = MetricQuery.file_share_sessions

    @classmethod
    def get_sql_expression(
        cls, t: ColumnElement[datetime], i: TimeInterval, now: datetime
    ) -> ColumnElement[int]:
        return func.cast(
            func.ceil(
                func.avg(FileShareSession.price_cents).filter(
                    FileShareSession.price_cents.is_not(None)
                )
            ),
            Integer,
        )

    @classmethod
    def get_cumulative(cls, periods: Iterable["MetricsPeriod"]) -> float:
        total_paid = sum(getattr(p, "file_share_paid_sessions") or 0 for p in periods)
        total_revenue = sum(getattr(p, "file_share_revenue") or 0 for p in periods)
        return total_revenue / total_paid if total_paid > 0 else 0.0


class FileSharePaymentConversionMetric(SQLMetric):
    slug = "file_share_payment_conversion"
    display_name = "Payment Conversion Rate"
    type = MetricType.percentage
    query = MetricQuery.file_share_sessions

    @classmethod
    def get_sql_expression(
        cls, t: ColumnElement[datetime], i: TimeInterval, now: datetime
    ) -> ColumnElement[float]:
        paid_sessions = func.count(FileShareSession.id).filter(
            FileShareSession.price_cents.is_not(None)
        )
        has_completed_payment = (
            select(func.count())
            .where(
                FileSharePayment.session_id == FileShareSession.id,
                FileSharePayment.status == FileSharePaymentStatus.completed,
            )
            .correlate(FileShareSession)
            .scalar_subquery()
        )
        sessions_with_payments = func.count(FileShareSession.id).filter(
            has_completed_payment > 0
        )
        return type_coerce(
            case(
                (paid_sessions == 0, 0),
                else_=type_coerce(sessions_with_payments, Float)
                / type_coerce(paid_sessions, Float),
            ),
            Float,
        )

    @classmethod
    def get_cumulative(cls, periods: Iterable["MetricsPeriod"]) -> float:
        return cumulative_last(periods, cls.slug)


class FileSharePlatformFeesMetric(SQLMetric):
    slug = "file_share_platform_fees"
    display_name = "File Share Platform Fees"
    type = MetricType.currency
    query = MetricQuery.file_share_sessions

    @classmethod
    def get_sql_expression(
        cls, t: ColumnElement[datetime], i: TimeInterval, now: datetime
    ) -> ColumnElement[int]:
        platform_fee_sum = (
            select(func.coalesce(func.sum(FileSharePayment.platform_fee_cents), 0))
            .where(
                FileSharePayment.session_id == FileShareSession.id,
                FileSharePayment.status == FileSharePaymentStatus.completed,
            )
            .correlate(FileShareSession)
            .scalar_subquery()
        )
        return func.coalesce(func.sum(platform_fee_sum), 0)

    @classmethod
    def get_cumulative(cls, periods: Iterable["MetricsPeriod"]) -> int | float:
        return cumulative_sum(periods, cls.slug)


class CumulativeFileSharePlatformFeesMetric(SQLMetric):
    slug = "cumulative_file_share_platform_fees"
    display_name = "Cumulative File Share Platform Fees"
    type = MetricType.currency
    query = MetricQuery.file_share_sessions

    get_sql_expression = FileSharePlatformFeesMetric.get_sql_expression

    @classmethod
    def get_cumulative(cls, periods: Iterable["MetricsPeriod"]) -> int | float:
        return cumulative_last(periods, cls.slug)


# ── Meta Metrics (Post-Compute) ──


class CashflowMetric(MetaMetric):
    slug = "cashflow"
    display_name = "Cashflow"
    type = MetricType.currency
    dependencies: ClassVar[list[str]] = ["file_share_revenue", "costs"]

    @classmethod
    def compute_from_period(cls, period: "MetricsPeriod") -> float:
        revenue = period.file_share_revenue or 0
        costs = period.costs or 0
        return revenue - costs

    @classmethod
    def get_cumulative(cls, periods: Iterable["MetricsPeriod"]) -> float:
        return cumulative_sum(periods, cls.slug)


# ── Metric Registries ──


METRICS_SQL: list[type[SQLMetric]] = [
    CostsMetric,
    CumulativeCostsMetric,
    CostPerUserMetric,
    ActiveUserMetric,
    FileShareSessionsMetric,
    FileShareDownloadsMetric,
    FileShareFreeSessionsMetric,
    FileShareActiveSessionsMetric,
    FileShareCompletedSessionsMetric,
    FileShareExpiredSessionsMetric,
    FileShareAvgDownloadsMetric,
    FileShareTotalSizeBytesMetric,
    CumulativeFileShareSessionsMetric,
    CumulativeFileShareDownloadsMetric,
    FileShareRevenueMetric,
    FileSharePaidSessionsMetric,
    FileShareAvgPriceMetric,
    FileSharePaymentConversionMetric,
    FileSharePlatformFeesMetric,
    CumulativeFileSharePlatformFeesMetric,
]

METRICS_POST_COMPUTE: list[type[MetaMetric]] = [
    CashflowMetric,
]

METRICS: list[type[Metric]] = [
    *METRICS_SQL,
    *METRICS_POST_COMPUTE,
]

__all__ = [
    "METRICS",
    "METRICS_POST_COMPUTE",
    "METRICS_SQL",
    "MetaMetric",
    "Metric",
    "MetricType",
    "SQLMetric",
]
