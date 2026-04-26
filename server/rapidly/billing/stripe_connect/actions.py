"""Stripe Connect account lifecycle service.

Handles Stripe Connect account creation (Express / Standard),
onboarding-link generation, dashboard-link generation, and
synchronisation of account status updates from Stripe webhooks.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import stripe as stripe_lib
import structlog

from rapidly.billing.account.queries import AccountRepository
from rapidly.errors import ErrorCode, RapidlyError, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import User, Workspace
from rapidly.platform.workspace.queries import WorkspaceRepository
from rapidly.postgres import AsyncReadSession

from .types import (
    StripeBalance,
    StripeBalanceAmount,
    StripePayout,
    StripePayoutList,
)

log = structlog.get_logger()


class StripeConnectServiceError(RapidlyError):
    pass


class StripeAccountNotConnected(StripeConnectServiceError):
    def __init__(self) -> None:
        super().__init__(
            "Stripe account is not connected",
            status_code=400,
            code=ErrorCode.BAD_REQUEST,
        )


# ── Account lookup ──


async def _get_stripe_account_id(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    workspace_id: UUID,
) -> str:
    org_repo = WorkspaceRepository.from_session(session)
    statement = org_repo.get_readable_statement(auth_subject).where(
        Workspace.id == workspace_id
    )
    workspace = await org_repo.get_one_or_none(statement)
    if workspace is None:
        raise ResourceNotFound()

    if workspace.account_id is None:
        raise StripeAccountNotConnected()

    account_repo = AccountRepository.from_session(session)
    account = await account_repo.get_by_id(workspace.account_id)
    if account is None or account.stripe_id is None:
        raise StripeAccountNotConnected()

    return account.stripe_id


# ── Balance ──


async def get_balance(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    workspace_id: UUID,
) -> StripeBalance:
    stripe_account_id = await _get_stripe_account_id(
        session, auth_subject, workspace_id
    )

    try:
        balance = await stripe_lib.Balance.retrieve_async(
            stripe_account=stripe_account_id
        )
    except stripe_lib.StripeError as e:
        log.error(
            "stripe_balance_error", stripe_account=stripe_account_id, error=str(e)
        )
        raise StripeConnectServiceError(
            f"Failed to retrieve balance: {e.user_message or 'Stripe error'}",
            status_code=502,
        ) from e

    return StripeBalance(
        available=[
            StripeBalanceAmount(amount=b.amount, currency=b.currency)
            for b in balance.available
        ],
        pending=[
            StripeBalanceAmount(amount=b.amount, currency=b.currency)
            for b in balance.pending
        ],
    )


# ── Payouts ──


async def list_payouts(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    workspace_id: UUID,
    *,
    created_gte: datetime | None = None,
    created_lte: datetime | None = None,
    limit: int = 20,
    starting_after: str | None = None,
) -> StripePayoutList:
    stripe_account_id = await _get_stripe_account_id(
        session, auth_subject, workspace_id
    )

    params: dict[str, Any] = {
        "stripe_account": stripe_account_id,
        "limit": limit,
    }
    if created_gte is not None:
        params["created"] = params.get("created", {})
        params["created"]["gte"] = int(created_gte.timestamp())
    if created_lte is not None:
        params["created"] = params.get("created", {})
        params["created"]["lte"] = int(created_lte.timestamp())
    if starting_after is not None:
        params["starting_after"] = starting_after

    try:
        result = await stripe_lib.Payout.list_async(**params)
    except stripe_lib.StripeError as e:
        log.error(
            "stripe_payouts_error", stripe_account=stripe_account_id, error=str(e)
        )
        raise StripeConnectServiceError(
            f"Failed to list payouts: {e.user_message or 'Stripe error'}",
            status_code=502,
        ) from e

    items = [
        StripePayout(
            id=p.id,
            amount=p.amount,
            currency=p.currency,
            status=p.status,
            arrival_date=datetime.fromtimestamp(p.arrival_date, tz=UTC),
            created=datetime.fromtimestamp(p.created, tz=UTC),
            description=p.description,
            method=p.method,
        )
        for p in result.data
    ]

    return StripePayoutList(items=items, has_more=result.has_more)
