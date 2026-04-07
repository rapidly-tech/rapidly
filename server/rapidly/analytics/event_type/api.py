"""Event-type HTTP endpoints: listing and label updates.

Exposes paginated listing of event types with aggregated occurrence
statistics, and PATCH-based label updates for existing event types.
"""

from uuid import UUID

from fastapi import Depends, Query

from rapidly.analytics.event_type import actions as event_type_service
from rapidly.analytics.event_type import ordering
from rapidly.analytics.event_type import permissions as auth
from rapidly.analytics.event_type import types as schemas
from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.core.types import MultipleQueryFilter
from rapidly.customers.customer.types.customer import CustomerID
from rapidly.errors import ResourceNotFound
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

router = APIRouter(prefix="/event-types", tags=["event-types", APITag.public])


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


@router.patch(
    "/{id}",
    response_model=schemas.EventType,
    summary="Update Event Type",
    description="Update an event type's label.",
    status_code=200,
    responses={404: {}},
)
async def update(
    id: schemas.EventTypeID,
    body: schemas.EventTypeUpdate,
    auth_subject: auth.EventTypeWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.EventType:
    existing = await event_type_service.get(session, auth_subject, id)
    if existing is None:
        raise ResourceNotFound()

    updated = await event_type_service.update(
        session, existing, body.label, body.label_property_selector
    )
    return schemas.EventType.model_validate(updated)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@router.get(
    "/",
    summary="List Event Types",
    response_model=PaginatedList[schemas.EventTypeWithStats],
)
async def list(
    auth_subject: auth.EventTypeRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.EventTypesSorting,
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
    query: str | None = Query(
        None,
        title="Query",
        description="Query to filter event types by name or label.",
    ),
    root_events: bool = Query(
        False,
        title="Root Events Filter",
        description="When true, only return event types with root events (parent_id IS NULL).",
    ),
    parent_id: UUID | None = Query(
        None,
        title="ParentID Filter",
        description="Filter by specific parent event ID.",
    ),
    source: EventSource | None = Query(
        None,
        title="EventSource Filter",
        description="Filter by event source (system or user).",
    ),
) -> PaginatedList[schemas.EventTypeWithStats]:
    """List event types with aggregated statistics."""
    results, count = await event_type_service.list_with_stats(
        session,
        auth_subject,
        workspace_id=workspace_id,
        customer_id=customer_id,
        external_customer_id=external_customer_id,
        query=query,
        root_events=root_events,
        parent_id=parent_id,
        source=source,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(results, count, pagination)
