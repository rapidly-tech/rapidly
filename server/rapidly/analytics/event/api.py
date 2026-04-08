"""Event HTTP endpoints: ingestion, listing, statistics, and sub-event trees.

Supports single and batch event creation, paginated listing with metadata
filters, time-bucketed statistics, and hierarchical sub-event retrieval
via the closure table.
"""

from collections.abc import Sequence
from datetime import date
from zoneinfo import ZoneInfo

from fastapi import Depends, Query
from pydantic import UUID4, AwareDatetime
from pydantic_extra_types.timezone_name import TimeZoneName

from rapidly.core.metadata import MetadataQuery, get_metadata_query_openapi_schema
from rapidly.core.pagination import (
    CursorPaginatedList,
    PaginatedList,
    PaginationParamsQuery,
)
from rapidly.core.time_queries import TimeInterval, is_under_limits
from rapidly.core.types import MultipleQueryFilter
from rapidly.customers.customer.types.customer import CustomerID
from rapidly.errors import RequestValidationError, ResourceNotFound, validation_error
from rapidly.models import Event
from rapidly.models.event import EventSource
from rapidly.openapi import APITag
from rapidly.platform.workspace.types import WorkspaceID
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.routing import APIRouter

from . import actions as event_service
from . import ordering
from . import permissions as auth
from .types import Event as EventSchema
from .types import (
    EventID,
    EventName,
    EventsIngest,
    EventsIngestResponse,
    EventTypeAdapter,
    ListStatisticsTimeseries,
)

router = APIRouter(prefix="/events", tags=["events", APITag.public])


EventNotFound = {"description": "Event not found.", "model": ResourceNotFound.schema()}

# Explicit allowlist of metadata field paths that may be used in aggregate queries.
# Only these fields are interpolated into SQL text() expressions.
ALLOWED_AGGREGATE_FIELDS: frozenset[str] = frozenset(
    {
        "_cost.amount",
        "cost.amount",
        "duration_ns",
        "tokens",
        "input_tokens",
        "output_tokens",
        "amount",
        "quantity",
        "count",
    }
)


def _validate_aggregate_fields(fields: Sequence[str]) -> None:
    """Reject aggregate_fields values that could cause SQL injection."""
    for field in fields:
        if field not in ALLOWED_AGGREGATE_FIELDS:
            raise RequestValidationError(
                [
                    validation_error(
                        "aggregate_fields",
                        f"Aggregate field {field!r} is not allowed. Permitted fields: {', '.join(sorted(ALLOWED_AGGREGATE_FIELDS))}.",
                        field,
                        loc_prefix="query",
                    )
                ]
            )


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------


@router.post("/ingest", summary="Ingest Events", status_code=201)
async def ingest(
    ingest: EventsIngest,
    auth_subject: auth.EventWrite,
    session: AsyncSession = Depends(get_db_session),
) -> EventsIngestResponse:
    """Ingest batch of events."""
    return await event_service.ingest(session, auth_subject, ingest)


# ---------------------------------------------------------------------------
# Single event
# ---------------------------------------------------------------------------


@router.get(
    "/{id}",
    summary="Get Event",
    response_model=EventSchema,
    responses={404: EventNotFound},
)
async def get(
    id: EventID,
    auth_subject: auth.EventRead,
    session: AsyncReadSession = Depends(get_db_read_session),
    aggregate_fields: Sequence[str] = Query(
        default=[],
        description=(
            "Metadata field paths to aggregate from descendants into ancestors "
            "(e.g., '_cost.amount', 'duration_ns'). Use dot notation for nested fields."
        ),
        include_in_schema=False,
    ),
) -> Event:
    """Get an event by ID."""
    _validate_aggregate_fields(aggregate_fields)
    event = await event_service.get(
        session, auth_subject, id, aggregate_fields=aggregate_fields
    )

    if event is None:
        raise ResourceNotFound()

    return event


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


@router.get(
    "/",
    summary="List Events",
    response_model=PaginatedList[EventSchema] | CursorPaginatedList[EventSchema],
    openapi_extra={"parameters": [get_metadata_query_openapi_schema()]},
)
async def list_events_endpoint(
    auth_subject: auth.EventRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.ListSorting,
    metadata: MetadataQuery,
    start_timestamp: AwareDatetime | None = Query(
        None, description="Filter events after this timestamp."
    ),
    end_timestamp: AwareDatetime | None = Query(
        None, description="Filter events before this timestamp."
    ),
    workspace_id: MultipleQueryFilter[WorkspaceID] | None = Query(
        None, title="WorkspaceID Filter", description="Filter by workspace ID."
    ),
    customer_id: MultipleQueryFilter[CustomerID] | None = Query(
        None, title="CustomerID Filter", description="Filter by customer ID."
    ),
    external_customer_id: MultipleQueryFilter[str] | None = Query(
        None,
        title="ExternalCustomerID Filter",
        description="Filter by external customer ID.",
    ),
    name: MultipleQueryFilter[str] | None = Query(
        None, title="Name Filter", description="Filter by event name."
    ),
    source: MultipleQueryFilter[EventSource] | None = Query(
        None, title="Source Filter", description="Filter by event source."
    ),
    event_type_id: UUID4 | None = Query(
        None,
        title="Event Type ID Filter",
        description="Filter by event type ID.",
        include_in_schema=False,
    ),
    query: str | None = Query(
        None, title="Query", description="Query to filter events."
    ),
    parent_id: EventID | None = Query(
        None,
        description="When combined with depth, use this event as the anchor instead of root events.",
    ),
    depth: int | None = Query(
        None,
        ge=0,
        le=5,
        description=(
            "Fetch descendants up to this depth. When set: 0=root events only, "
            "1=roots+children, etc. Max 5. When not set, returns all events."
        ),
    ),
    aggregate_fields: Sequence[str] = Query(
        default=[],
        description=(
            "Metadata field paths to aggregate from descendants into ancestors "
            "(e.g., '_cost.amount', 'duration_ns'). Use dot notation for nested fields."
        ),
        include_in_schema=False,
    ),
    cursor_pagination: bool = Query(
        False,
        title="Use cursor pagination",
        description=(
            "Use cursor-based pagination (has_next_page) instead of offset pagination. "
            "Faster for large datasets."
        ),
        include_in_schema=False,
    ),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> PaginatedList[EventSchema] | CursorPaginatedList[EventSchema]:
    """List events."""
    _validate_aggregate_fields(aggregate_fields)

    if query is not None and workspace_id is None:
        raise RequestValidationError(
            [
                {
                    "type": "query",
                    "loc": ("query", "query"),
                    "msg": "Query is only supported when workspace_id is provided.",
                    "input": query,
                }
            ]
        )

    results, count = await event_service.list_events(
        session,
        auth_subject,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        workspace_id=workspace_id,
        customer_id=customer_id,
        external_customer_id=external_customer_id,
        name=name,
        source=source,
        event_type_id=event_type_id,
        metadata=metadata,
        pagination=pagination,
        sorting=sorting,
        query=query,
        parent_id=parent_id,
        depth=depth,
        aggregate_fields=aggregate_fields,
        cursor_pagination=cursor_pagination,
    )

    validated = [EventTypeAdapter.validate_python(r) for r in results]

    if cursor_pagination:
        return CursorPaginatedList.from_results(validated, count > 0)

    return PaginatedList.from_paginated_results(validated, count, pagination)


# ---------------------------------------------------------------------------
# Event names
# ---------------------------------------------------------------------------


@router.get(
    "/names", summary="List Event Names", response_model=PaginatedList[EventName]
)
async def list_names(
    auth_subject: auth.EventRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.EventNamesSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    workspace_id: MultipleQueryFilter[WorkspaceID] | None = Query(
        None, title="WorkspaceID Filter", description="Filter by workspace ID."
    ),
    customer_id: MultipleQueryFilter[CustomerID] | None = Query(
        None, title="CustomerID Filter", description="Filter by customer ID."
    ),
    external_customer_id: MultipleQueryFilter[str] | None = Query(
        None,
        title="ExternalCustomerID Filter",
        description="Filter by external customer ID.",
    ),
    source: MultipleQueryFilter[EventSource] | None = Query(
        None, title="Source Filter", description="Filter by event source."
    ),
    query: str | None = Query(
        None, title="Query", description="Query to filter event names."
    ),
) -> PaginatedList[EventName]:
    """List event names."""
    results, count = await event_service.list_names(
        session,
        auth_subject,
        workspace_id=workspace_id,
        customer_id=customer_id,
        external_customer_id=external_customer_id,
        source=source,
        query=query,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(results, count, pagination)


# ---------------------------------------------------------------------------
# Time-series statistics
# ---------------------------------------------------------------------------


@router.get(
    "/statistics/timeseries",
    summary="List statistics timeseries",
    openapi_extra={"parameters": [get_metadata_query_openapi_schema()]},
    tags=[APITag.private],
    response_model=ListStatisticsTimeseries,
)
async def list_statistics_timeseries(
    auth_subject: auth.EventRead,
    metadata: MetadataQuery,
    hierarchy_sorting: ordering.EventStatisticsSorting,
    start_date: date = Query(
        ...,
        description="Start date.",
    ),
    end_date: date = Query(..., description="End date."),
    timezone: TimeZoneName = Query(
        default="UTC",
        description="Timezone to use for the dates. Default is UTC.",
    ),
    interval: TimeInterval = Query(..., description="Interval between two dates."),
    workspace_id: MultipleQueryFilter[WorkspaceID] | None = Query(
        None, title="WorkspaceID Filter", description="Filter by workspace ID."
    ),
    customer_id: MultipleQueryFilter[CustomerID] | None = Query(
        None, title="CustomerID Filter", description="Filter by customer ID."
    ),
    external_customer_id: MultipleQueryFilter[str] | None = Query(
        None,
        title="ExternalCustomerID Filter",
        description="Filter by external customer ID.",
    ),
    name: MultipleQueryFilter[str] | None = Query(
        None, title="Name Filter", description="Filter by event name."
    ),
    source: MultipleQueryFilter[EventSource] | None = Query(
        None, title="Source Filter", description="Filter by event source."
    ),
    event_type_id: UUID4 | None = Query(
        None,
        title="Event Type ID Filter",
        description="Filter by event type ID.",
    ),
    query: str | None = Query(
        None, title="Query", description="Query to filter events."
    ),
    aggregate_fields: Sequence[str] = Query(
        default=["_cost.amount"],
        description=(
            "Metadata field paths to aggregate (e.g., '_cost.amount', 'duration_ns'). "
            "Use dot notation for nested fields."
        ),
    ),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> ListStatisticsTimeseries:
    """
    Get aggregate statistics grouped by root event name over time.

    Returns time series data with periods and totals, similar to the metrics endpoint.
    Each period contains stats grouped by event name, and totals show overall stats
    across all periods.
    """
    _validate_aggregate_fields(aggregate_fields)

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

    if query is not None and workspace_id is None:
        raise RequestValidationError(
            [
                {
                    "type": "query",
                    "loc": ("query", "query"),
                    "msg": "Query is only supported when workspace_id is provided.",
                    "input": query,
                }
            ]
        )

    return await event_service.list_statistics_timeseries(
        session,
        auth_subject,
        start_date=start_date,
        end_date=end_date,
        timezone=ZoneInfo(timezone),
        interval=interval,
        workspace_id=workspace_id,
        customer_id=customer_id,
        external_customer_id=external_customer_id,
        name=name,
        source=source,
        event_type_id=event_type_id,
        metadata=metadata,
        query=query,
        aggregate_fields=tuple(aggregate_fields),
        hierarchy_stats_sorting=hierarchy_sorting,
    )
