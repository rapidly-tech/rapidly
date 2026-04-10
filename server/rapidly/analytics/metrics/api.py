"""Metrics HTTP endpoints: time-bucketed analytics and interval limits.

Returns period-over-period counts and revenue totals for a workspace,
supporting configurable date ranges, timezone offsets, and metric-type
selection for improved query performance.
"""

from datetime import date
from zoneinfo import ZoneInfo

from fastapi import Depends, Query
from pydantic_extra_types.timezone_name import TimeZoneName

from rapidly.catalog.share.types import ShareID
from rapidly.core.time_queries import (
    MAX_INTERVAL_DAYS,
    MIN_DATE,
    MIN_INTERVAL_DAYS,
    TimeInterval,
    is_under_limits,
)
from rapidly.core.types import MultipleQueryFilter
from rapidly.customers.customer.types.customer import CustomerID
from rapidly.errors import RequestValidationError, validation_error
from rapidly.openapi import APITag
from rapidly.platform.workspace.types import WorkspaceID
from rapidly.postgres import AsyncReadSession, get_db_read_session
from rapidly.routing import APIRouter

from . import actions as metrics_service
from . import permissions as auth
from .metrics import METRICS
from .types import MetricsLimits, MetricsResponse

router = APIRouter(prefix="/metrics", tags=["metrics", APITag.public, APITag.mcp])


# ---------------------------------------------------------------------------
# Interval limits
# ---------------------------------------------------------------------------


@router.get("/limits", summary="Get Metrics Limits", response_model=MetricsLimits)
async def limits(auth_subject: auth.MetricsRead) -> MetricsLimits:
    """Return the allowed day-ranges for each time interval."""
    return MetricsLimits.model_validate(
        {
            "min_date": MIN_DATE,
            "intervals": {
                iv.value: {
                    "min_days": MIN_INTERVAL_DAYS[iv],
                    "max_days": MAX_INTERVAL_DAYS[iv],
                }
                for iv in TimeInterval
            },
        }
    )


# ---------------------------------------------------------------------------
# Dashboard metrics
# ---------------------------------------------------------------------------


@router.get(
    "/",
    summary="Get Metrics",
    response_model=MetricsResponse,
    response_model_exclude_none=True,
)
async def get(
    auth_subject: auth.MetricsRead,
    start_date: date = Query(
        ...,
        description="Start date.",
    ),
    end_date: date = Query(..., description="End date."),
    timezone: TimeZoneName = Query(
        default="UTC",
        description="Timezone to use for the timestamps. Default is UTC.",
    ),
    interval: TimeInterval = Query(..., description="Interval between two timestamps."),
    workspace_id: MultipleQueryFilter[WorkspaceID] | None = Query(
        None, title="WorkspaceID Filter", description="Filter by workspace ID."
    ),
    share_id: MultipleQueryFilter[ShareID] | None = Query(
        None, title="ShareID Filter", description="Filter by share ID."
    ),
    customer_id: MultipleQueryFilter[CustomerID] | None = Query(
        None, title="CustomerID Filter", description="Filter by customer ID."
    ),
    metrics: list[str] | None = Query(
        None,
        title="Metrics",
        description=(
            "List of metric slugs to focus on. "
            "When provided, only the queries needed for these metrics will be executed, "
            "improving performance. If not provided, all metrics are returned."
        ),
    ),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> MetricsResponse:
    """
    Get metrics about your file shares and costs.

    Currency values are output in cents.
    """
    _validate_interval(start_date, end_date, interval)
    _validate_metric_slugs(metrics)

    return await metrics_service.get_metrics(
        session,
        auth_subject,
        start_date=start_date,
        end_date=end_date,
        timezone=ZoneInfo(timezone),
        interval=interval,
        workspace_id=workspace_id,
        share_id=share_id,
        customer_id=customer_id,
        metrics=metrics,
    )


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_interval(
    start_date: date, end_date: date, interval: TimeInterval
) -> None:
    if not is_under_limits(start_date, end_date, interval):
        raise RequestValidationError(
            [
                {
                    "loc": ("query",),
                    "msg": (
                        "The interval is too big. "
                        "Try to change the interval or reduce the date range."
                    ),
                    "type": "value_error",
                    "input": (start_date, end_date, interval),
                }
            ]
        )


def _validate_metric_slugs(slugs: list[str] | None) -> None:
    if slugs is None:
        return

    known_slugs = {m.slug for m in METRICS}
    unknown = set(slugs) - known_slugs
    if unknown:
        raise RequestValidationError(
            [
                validation_error(
                    "metrics",
                    f"Invalid metric slugs: {', '.join(sorted(unknown))}",
                    slugs,
                    loc_prefix="query",
                )
            ]
        )
