"""Webhook endpoint HTTP routes: CRUD, delivery history, and re-delivery.

Provides full lifecycle management for webhook endpoints within a
workspace, paginated delivery-log queries for monitoring reliability,
and on-demand re-delivery of failed webhook events.
"""

from typing import Annotated, Literal

from fastapi import Depends, Path, Query
from pydantic import UUID4, AwareDatetime

from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.core.types import MultipleQueryFilter
from rapidly.errors import ResourceNotFound
from rapidly.models import WebhookEndpoint
from rapidly.models.webhook_endpoint import WebhookEventType
from rapidly.openapi import APITag
from rapidly.platform.workspace.types import WorkspaceID
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.routing import APIRouter

from . import actions as webhook_service
from .permissions import WebhooksRead, WebhooksWrite
from .types import WebhookDelivery as WebhookDeliverySchema
from .types import WebhookEndpoint as WebhookEndpointSchema
from .types import WebhookEndpointCreate, WebhookEndpointUpdate

router = APIRouter(prefix="/webhooks", tags=["webhooks", APITag.public])

WebhookEndpointID = Annotated[UUID4, Path(description="The webhook endpoint ID.")]
WebhookEndpointNotFound = {
    "description": "Webhook endpoint not found.",
    "model": ResourceNotFound.schema(),
}


# ---------------------------------------------------------------------------
# Re-delivery
# ---------------------------------------------------------------------------


@router.post(
    "/events/{id}/redeliver",
    status_code=202,
    responses={
        202: {"description": "Webhook event re-delivery scheduled."},
        404: {
            "description": "Webhook event not found.",
            "model": ResourceNotFound.schema(),
        },
    },
)
async def redeliver_webhook_event(
    id: Annotated[UUID4, Path(..., description="The webhook event ID.")],
    auth_subject: WebhooksWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Schedule the re-delivery of a webhook event."""
    return await webhook_service.redeliver_event(session, auth_subject, id)


# ---------------------------------------------------------------------------
# Deliveries
# ---------------------------------------------------------------------------


@router.get(
    "/deliveries",
    response_model=PaginatedList[WebhookDeliverySchema],
)
async def list_webhook_deliveries(
    pagination: PaginationParamsQuery,
    auth_subject: WebhooksRead,
    endpoint_id: MultipleQueryFilter[UUID4] | None = Query(
        None, description="Filter by webhook endpoint ID."
    ),
    start_timestamp: AwareDatetime | None = Query(
        None, description="Filter deliveries after this timestamp."
    ),
    end_timestamp: AwareDatetime | None = Query(
        None, description="Filter deliveries before this timestamp."
    ),
    succeeded: bool | None = Query(
        None, description="Filter by delivery success status."
    ),
    query: str | None = Query(
        None,
        description="Query to filter webhook deliveries.",
    ),
    http_code_class: Literal["2xx", "3xx", "4xx", "5xx"] | None = Query(
        None, description="Filter by HTTP response code class (2xx, 3xx, 4xx, 5xx)."
    ),
    event_type: MultipleQueryFilter[WebhookEventType] | None = Query(
        None, description="Filter by webhook event type."
    ),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> PaginatedList[WebhookDeliverySchema]:
    """
    List webhook deliveries.

    Deliveries are all the attempts to deliver a webhook event to an endpoint.
    """
    results, count = await webhook_service.list_deliveries(
        session,
        auth_subject,
        endpoint_id=endpoint_id,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        succeeded=succeeded,
        query=query,
        http_code_class=http_code_class,
        event_type=event_type,
        pagination=pagination,
    )

    return PaginatedList.from_paginated_results(
        [WebhookDeliverySchema.model_validate(r) for r in results],
        count,
        pagination,
    )


# ---------------------------------------------------------------------------
# Endpoint CRUD
# ---------------------------------------------------------------------------


@router.get("/endpoints", response_model=PaginatedList[WebhookEndpointSchema])
async def list_webhook_endpoints(
    pagination: PaginationParamsQuery,
    auth_subject: WebhooksRead,
    workspace_id: MultipleQueryFilter[WorkspaceID] | None = Query(
        None, description="Filter by workspace ID."
    ),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> PaginatedList[WebhookEndpointSchema]:
    """List webhook endpoints."""
    results, count = await webhook_service.list_endpoints(
        session,
        auth_subject,
        workspace_id=workspace_id,
        pagination=pagination,
    )
    return PaginatedList.from_paginated_results(
        [WebhookEndpointSchema.model_validate(r) for r in results],
        count,
        pagination,
    )


@router.get(
    "/endpoints/{id}",
    response_model=WebhookEndpointSchema,
    responses={404: WebhookEndpointNotFound},
)
async def get_webhook_endpoint(
    id: WebhookEndpointID,
    auth_subject: WebhooksRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> WebhookEndpoint:
    """Get a webhook endpoint by ID."""
    found = await webhook_service.get_endpoint(session, auth_subject, id)
    if not found:
        raise ResourceNotFound()

    return found


@router.post(
    "/endpoints",
    response_model=WebhookEndpointSchema,
    status_code=201,
    responses={201: {"description": "Webhook endpoint created."}},
)
async def create_webhook_endpoint(
    endpoint_create: WebhookEndpointCreate,
    auth_subject: WebhooksWrite,
    session: AsyncSession = Depends(get_db_session),
) -> WebhookEndpoint:
    """Create a webhook endpoint."""
    return await webhook_service.create_endpoint(session, auth_subject, endpoint_create)


@router.patch(
    "/endpoints/{id}",
    response_model=WebhookEndpointSchema,
    responses={
        200: {"description": "Webhook endpoint updated."},
        404: WebhookEndpointNotFound,
    },
)
async def update_webhook_endpoint(
    id: WebhookEndpointID,
    update: WebhookEndpointUpdate,
    auth_subject: WebhooksWrite,
    session: AsyncSession = Depends(get_db_session),
) -> WebhookEndpoint:
    """Update a webhook endpoint."""
    found = await webhook_service.get_endpoint(session, auth_subject, id)
    if not found:
        raise ResourceNotFound()

    return await webhook_service.update_endpoint(
        session, endpoint=found, update_schema=update
    )


@router.patch(
    "/endpoints/{id}/secret",
    response_model=WebhookEndpointSchema,
    responses={
        200: {"description": "Webhook endpoint secret reset."},
        404: WebhookEndpointNotFound,
    },
)
async def reset_webhook_endpoint_secret(
    id: WebhookEndpointID,
    auth_subject: WebhooksWrite,
    session: AsyncSession = Depends(get_db_session),
) -> WebhookEndpoint:
    """Regenerate a webhook endpoint secret."""
    found = await webhook_service.get_endpoint(session, auth_subject, id)
    if not found:
        raise ResourceNotFound()

    return await webhook_service.reset_endpoint_secret(session, endpoint=found)


@router.delete(
    "/endpoints/{id}",
    status_code=204,
    responses={
        204: {"description": "Webhook endpoint deleted."},
        404: WebhookEndpointNotFound,
    },
)
async def delete_webhook_endpoint(
    id: WebhookEndpointID,
    auth_subject: WebhooksWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a webhook endpoint."""
    found = await webhook_service.get_endpoint(session, auth_subject, id)
    if not found:
        raise ResourceNotFound()

    await webhook_service.delete_endpoint(session, found)
