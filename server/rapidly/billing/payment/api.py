"""Payment HTTP routes: listing and detail views.

Provides paginated payment listing scoped to an workspace and
individual payment detail look-up, including method information
and Stripe metadata.
"""

from fastapi import Depends, Query

from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.core.types import MultipleQueryFilter
from rapidly.errors import ResourceNotFound
from rapidly.models import Payment
from rapidly.models.payment import PaymentStatus
from rapidly.openapi import APITag
from rapidly.platform.workspace.types import WorkspaceID
from rapidly.postgres import AsyncReadSession, get_db_read_session
from rapidly.routing import APIRouter

from . import actions as payment_service
from . import ordering
from . import permissions as auth
from .types import Payment as PaymentSchema
from .types import PaymentAdapter, PaymentID

router = APIRouter(prefix="/payments", tags=["payments", APITag.public, APITag.mcp])


PaymentNotFound = {
    "description": "Payment not found.",
    "model": ResourceNotFound.schema(),
}


@router.get("/", summary="List Payments", response_model=PaginatedList[PaymentSchema])
async def list(
    auth_subject: auth.PaymentRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.ListSorting,
    workspace_id: MultipleQueryFilter[WorkspaceID] | None = Query(
        None, title="WorkspaceID Filter", description="Filter by workspace ID."
    ),
    status: MultipleQueryFilter[PaymentStatus] | None = Query(
        None, title="Status Filter", description="Filter by payment status."
    ),
    method: MultipleQueryFilter[str] | None = Query(
        None, title="Method Filter", description="Filter by payment method."
    ),
    customer_email: MultipleQueryFilter[str] | None = Query(
        None, title="CustomerEmail Filter", description="Filter by customer email."
    ),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> PaginatedList[PaymentSchema]:
    """List payments."""
    results, count = await payment_service.list(
        session,
        auth_subject,
        workspace_id=workspace_id,
        status=status,
        method=method,
        customer_email=customer_email,
        pagination=pagination,
        sorting=sorting,
    )

    return PaginatedList.from_paginated_results(
        [PaymentAdapter.validate_python(result) for result in results],
        count,
        pagination,
    )


@router.get(
    "/{id}",
    summary="Get Payment",
    response_model=PaymentSchema,
    responses={404: PaymentNotFound},
)
async def get(
    id: PaymentID,
    auth_subject: auth.PaymentRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> Payment:
    """Get a payment by ID."""
    payment = await payment_service.get(session, auth_subject, id)

    if payment is None:
        raise ResourceNotFound()

    return payment
