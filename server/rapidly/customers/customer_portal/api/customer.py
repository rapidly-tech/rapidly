"""Customer-portal customer routes: profile, events, and SSE streaming.

Exposes the authenticated customer's profile data and a server-sent
events endpoint for real-time dashboard updates within the portal.
"""

import structlog
from fastapi import Depends, Request
from sse_starlette import EventSourceResponse

from rapidly.analytics.eventstream.actions import Receivers
from rapidly.analytics.eventstream.api import subscribe
from rapidly.models import Customer
from rapidly.openapi import APITag
from rapidly.postgres import AsyncSession, get_db_session
from rapidly.redis import Redis, get_redis
from rapidly.routing import APIRouter

from .. import permissions as auth
from ..actions.customer import customer as customer_service
from ..types.customer import (
    CustomerPortalCustomer,
    CustomerPortalCustomerUpdate,
)
from ..utils import get_customer, get_customer_id

_log = structlog.get_logger()

router = APIRouter(prefix="/customers", tags=["customers", APITag.public])


@router.get("/stream", include_in_schema=False)
async def stream(
    request: Request,
    auth_subject: auth.CustomerPortalUnionRead,
    session: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> EventSourceResponse:
    receivers = Receivers(customer_id=get_customer_id(auth_subject))
    channels = receivers.get_channels()
    return EventSourceResponse(subscribe(redis, channels, request))


@router.get("/me", summary="Get Customer", response_model=CustomerPortalCustomer)
async def get(auth_subject: auth.CustomerPortalUnionRead) -> Customer:
    """Get authenticated customer."""
    return get_customer(auth_subject)


@router.patch(
    "/me",
    summary="Update Customer",
    responses={
        200: {"description": "Customer updated."},
    },
    response_model=CustomerPortalCustomer,
)
async def update(
    customer_update: CustomerPortalCustomerUpdate,
    auth_subject: auth.CustomerPortalUnionBillingWrite,
    session: AsyncSession = Depends(get_db_session),
) -> Customer:
    """Update authenticated customer."""
    return await customer_service.update(
        session, get_customer(auth_subject), customer_update
    )
