"""SQL query builders for time-bucketed metric aggregation.

Constructs CTEs and window-function queries that bucket events,
payments, and customers into configurable time intervals (day, week,
month, year) for the analytics dashboard.

``MetricsQueryService`` encapsulates the final statement assembly and
streaming execution so that ``actions.py`` remains free of inline SQL.
"""

import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, Self

from sqlalchemy import (
    CTE,
    ColumnElement,
    FromClause,
    Row,
    Select,
    and_,
    cte,
    func,
    or_,
    select,
    text,
)

from rapidly.config import settings
from rapidly.core.time_queries import TimeInterval
from rapidly.identity.auth.models import (
    AuthPrincipal,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import (
    Customer,
    Event,
    FileShareSession,
    User,
    Workspace,
    WorkspaceMembership,
)
from rapidly.postgres import AsyncReadSession, AsyncSession

if TYPE_CHECKING:
    from .metrics import SQLMetric


# ── Query definitions ──


class MetricQuery(StrEnum):
    events = "events"
    file_share_sessions = "file_share_sessions"


class QueryCallable(Protocol):
    def __call__(
        self,
        timestamp_series: CTE,
        interval: TimeInterval,
        auth_subject: AuthPrincipal[User | Workspace],
        metrics: list["type[SQLMetric]"],
        now: datetime,
        *,
        bounds: tuple[datetime, datetime],
        workspace_id: Sequence[uuid.UUID] | None = None,
        share_id: Sequence[uuid.UUID] | None = None,
        customer_id: Sequence[uuid.UUID] | None = None,
    ) -> CTE: ...


# ── Query builders ──


def get_events_metrics_cte(
    timestamp_series: CTE,
    interval: TimeInterval,
    auth_subject: AuthPrincipal[User | Workspace],
    metrics: list["type[SQLMetric]"],
    now: datetime,
    *,
    bounds: tuple[datetime, datetime],
    workspace_id: Sequence[uuid.UUID] | None = None,
    customer_id: Sequence[uuid.UUID] | None = None,
    share_id: Sequence[uuid.UUID] | None = None,
) -> CTE:
    start_timestamp, end_timestamp = bounds
    timestamp_column: ColumnElement[datetime] = timestamp_series.c.timestamp
    day_column = interval.sql_date_trunc(Event.timestamp)

    daily_statement = (
        select(
            day_column.label("day"),
            *[
                func.coalesce(
                    metric.get_sql_expression(day_column, interval, now), 0
                ).label(metric.slug)
                for metric in metrics
                if metric.query == MetricQuery.events
            ],
        )
        .select_from(Event)
        .where(
            Event.timestamp >= start_timestamp,
            Event.timestamp <= end_timestamp,
        )
    )

    # Apply workspace filter
    if workspace_id is not None:
        if len(workspace_id) == 1:
            daily_statement = daily_statement.where(
                Event.workspace_id == workspace_id[0]
            )
        else:
            daily_statement = daily_statement.where(
                Event.workspace_id.in_(workspace_id)
            )
    elif is_workspace_principal(auth_subject):
        daily_statement = daily_statement.where(
            Event.workspace_id == auth_subject.subject.id
        )
    elif is_user_principal(auth_subject):
        daily_statement = daily_statement.where(
            Event.workspace_id.in_(
                select(WorkspaceMembership.workspace_id).where(
                    WorkspaceMembership.user_id == auth_subject.subject.id,
                    WorkspaceMembership.deleted_at.is_(None),
                )
            )
        )

    # Apply customer filter
    if customer_id is not None:
        daily_statement = daily_statement.join(
            Customer,
            onclause=or_(
                Event.customer_id == Customer.id,
                and_(
                    Customer.external_id.is_not(None),
                    Event.external_customer_id == Customer.external_id,
                    Event.workspace_id == Customer.workspace_id,
                ),
            ),
        ).where(Customer.id.in_(customer_id))

    daily_statement = daily_statement.group_by(day_column)
    daily_metrics = cte(daily_statement)

    return cte(
        select(
            timestamp_column.label("timestamp"),
            *[
                (
                    func.coalesce(
                        func.sum(getattr(daily_metrics.c, metric.slug)).over(
                            order_by=timestamp_column
                        ),
                        0,
                    )
                    if metric.slug == "cumulative_costs"
                    else func.coalesce(getattr(daily_metrics.c, metric.slug), 0)
                ).label(metric.slug)
                for metric in metrics
                if metric.query == MetricQuery.events
            ],
        )
        .select_from(
            timestamp_series.join(
                daily_metrics,
                onclause=daily_metrics.c.day == timestamp_column,
                isouter=True,
            )
        )
        .order_by(timestamp_column.asc())
    )


def _get_readable_file_share_sessions_statement(
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    workspace_id: Sequence[uuid.UUID] | None = None,
) -> Select[tuple[uuid.UUID]]:
    statement = select(FileShareSession.id)

    if is_user_principal(auth_subject):
        statement = statement.where(
            FileShareSession.workspace_id.in_(
                select(WorkspaceMembership.workspace_id).where(
                    WorkspaceMembership.user_id == auth_subject.subject.id,
                    WorkspaceMembership.deleted_at.is_(None),
                )
            )
        )
    elif is_workspace_principal(auth_subject):
        statement = statement.where(
            FileShareSession.workspace_id == auth_subject.subject.id
        )

    if workspace_id is not None:
        statement = statement.where(FileShareSession.workspace_id.in_(workspace_id))

    return statement


def get_file_share_sessions_metrics_cte(
    timestamp_series: CTE,
    interval: TimeInterval,
    auth_subject: AuthPrincipal[User | Workspace],
    metrics: list["type[SQLMetric]"],
    now: datetime,
    *,
    bounds: tuple[datetime, datetime],
    workspace_id: Sequence[uuid.UUID] | None = None,
    share_id: Sequence[uuid.UUID] | None = None,
    customer_id: Sequence[uuid.UUID] | None = None,
) -> CTE:
    start_timestamp, end_timestamp = bounds
    timestamp_column: ColumnElement[datetime] = timestamp_series.c.timestamp

    readable_sessions_statement = _get_readable_file_share_sessions_statement(
        auth_subject,
        workspace_id=workspace_id,
    )

    day_column = interval.sql_date_trunc(FileShareSession.created_at)

    cumulative_file_share_metrics = [
        "cumulative_file_share_platform_fees",
        "cumulative_file_share_sessions",
        "cumulative_file_share_downloads",
    ]

    daily_metrics = cte(
        select(
            day_column.label("day"),
            *[
                func.coalesce(
                    metric.get_sql_expression(day_column, interval, now), 0
                ).label(metric.slug)
                for metric in metrics
                if metric.query == MetricQuery.file_share_sessions
            ],
        )
        .select_from(FileShareSession)
        .where(
            FileShareSession.id.in_(readable_sessions_statement),
            FileShareSession.created_at >= start_timestamp,
            FileShareSession.created_at <= end_timestamp,
        )
        .group_by(day_column)
    )

    return cte(
        select(
            timestamp_column.label("timestamp"),
            *[
                (
                    func.coalesce(
                        func.sum(getattr(daily_metrics.c, metric.slug)).over(
                            order_by=timestamp_column
                        ),
                        0,
                    )
                    if metric.slug in cumulative_file_share_metrics
                    else func.coalesce(getattr(daily_metrics.c, metric.slug), 0)
                ).label(metric.slug)
                for metric in metrics
                if metric.query == MetricQuery.file_share_sessions
            ],
        )
        .select_from(
            timestamp_series.join(
                daily_metrics,
                onclause=daily_metrics.c.day == timestamp_column,
                isouter=True,
            )
        )
        .order_by(timestamp_column.asc())
    )


QUERIES: list[QueryCallable] = [
    get_events_metrics_cte,
    get_file_share_sessions_metrics_cte,
]

# Mapping from MetricQuery enum to query function for filtering
QUERY_TO_FUNCTION: dict[MetricQuery, QueryCallable] = {
    MetricQuery.events: get_events_metrics_cte,
    MetricQuery.file_share_sessions: get_file_share_sessions_metrics_cte,
}


# ── Metrics query service ──


class MetricsQueryService:
    """Assembles the final metrics SELECT from per-domain CTEs and streams results.

    This keeps all ``select()`` construction and ``session.execute/stream``
    calls inside the queries layer, as required by codebase conventions.
    """

    __slots__ = ("session",)

    def __init__(self, session: AsyncSession | AsyncReadSession) -> None:
        self.session = session

    @classmethod
    def from_session(cls, session: AsyncSession | AsyncReadSession) -> Self:
        return cls(session)

    # -- session configuration ------------------------------------------------

    async def configure_session_timezone(self, timezone_key: str) -> None:
        """Set the PostgreSQL session timezone for correct time-bucketing."""
        await self.session.execute(
            select(func.set_config("TimeZone", timezone_key, True))
        )
        await self.session.execute(
            text("SET LOCAL plan_cache_mode = 'force_custom_plan'")
        )

    # -- statement building ---------------------------------------------------

    @staticmethod
    def build_metrics_statement(
        timestamp_series: CTE,
        query_ctes: Sequence[CTE],
    ) -> Select[Any]:
        """Join per-domain CTEs against the timestamp series into a single SELECT.

        Each CTE in *query_ctes* is expected to carry a ``timestamp`` column
        that aligns with the series.  The result is ordered by timestamp
        ascending.
        """
        timestamp_column: ColumnElement[datetime] = timestamp_series.c.timestamp

        from_query: FromClause = timestamp_series
        for query_cte in query_ctes:
            from_query = from_query.join(
                query_cte,
                onclause=query_cte.c.timestamp == timestamp_column,
            )

        return (
            select(
                timestamp_column.label("timestamp"),
                *query_ctes,
            )
            .select_from(from_query)
            .order_by(timestamp_column.asc())
        )

    # -- execution ------------------------------------------------------------

    async def stream_metrics(
        self,
        statement: Select[Any],
    ) -> AsyncIterator[Row[Any]]:
        """Execute *statement* as a server-side cursor and yield rows."""
        result = await self.session.stream(
            statement,
            execution_options={"yield_per": settings.DATABASE_STREAM_YIELD_PER},
        )
        async for row in result:
            yield row
