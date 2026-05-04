"""Stripe Connect webhook ingestion routes.

Receives incoming Stripe Connect webhook events, verifies their
signature, and dispatches them to the appropriate background handler.
"""

from datetime import datetime

from fastapi import Depends, Query

from rapidly.openapi import APITag
from rapidly.platform.workspace.types import WorkspaceID
from rapidly.postgres import AsyncReadSession, get_db_read_session
from rapidly.routing import APIRouter

from . import actions as stripe_connect_service
from . import permissions as auth
from .types import StripeBalance, StripePayoutList

router = APIRouter(
    prefix="/stripe-connect",
    tags=["stripe_connect", APITag.private],
)


@router.get(
    "/balance",
    response_model=StripeBalance,
    summary="Get Stripe Balance",
)
async def get_balance(
    auth_subject: auth.StripeConnectRead,
    workspace_id: WorkspaceID = Query(
        ..., description="Workspace ID to get balance for"
    ),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> StripeBalance:
    return await stripe_connect_service.get_balance(session, auth_subject, workspace_id)


@router.get(
    "/payouts",
    response_model=StripePayoutList,
    summary="List Stripe Payouts",
)
async def list_payouts(
    auth_subject: auth.StripeConnectRead,
    workspace_id: WorkspaceID = Query(
        ..., description="Workspace ID to list payouts for"
    ),
    created_gte: datetime | None = Query(
        None, description="Filter payouts created on or after this date"
    ),
    created_lte: datetime | None = Query(
        None, description="Filter payouts created on or before this date"
    ),
    limit: int = Query(20, ge=1, le=100, description="Number of payouts to return"),
    starting_after: str | None = Query(
        None, description="Stripe payout ID to start after (for pagination)"
    ),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> StripePayoutList:
    return await stripe_connect_service.list_payouts(
        session,
        auth_subject,
        workspace_id,
        created_gte=created_gte,
        created_lte=created_lte,
        limit=limit,
        starting_after=starting_after,
    )
