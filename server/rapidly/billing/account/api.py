"""Account (Stripe Connect) HTTP routes: onboarding, dashboard links, and listing.

Provides endpoints for creating a Stripe Connect account, generating
onboarding and dashboard links, and listing accounts associated with
the authenticated user's workspaces.
"""

from uuid import UUID

from fastapi import Depends, Query

from rapidly.core.http import get_safe_return_url
from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.enums import AccountType
from rapidly.errors import InternalServerError, ResourceNotFound
from rapidly.models import Account
from rapidly.openapi import APITag
from rapidly.platform.workspace import actions as workspace_service
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.routing import APIRouter

from . import actions as account_service
from .permissions import AccountRead, AccountWrite
from .types import Account as AccountSchema
from .types import AccountCreateForWorkspace, AccountLink, AccountUpdate

router = APIRouter(tags=["accounts", APITag.private])


# ── List ──


@router.get("/accounts/search", response_model=PaginatedList[AccountSchema])
async def search(
    auth_subject: AccountRead,
    pagination: PaginationParamsQuery,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> PaginatedList[AccountSchema]:
    results, count = await account_service.search(
        session, auth_subject, pagination=pagination
    )

    return PaginatedList.from_paginated_results(
        [AccountSchema.model_validate(result) for result in results],
        count,
        pagination,
    )


# ── Detail ──


@router.get("/accounts/{id}", response_model=AccountSchema)
async def get(
    id: UUID,
    auth_subject: AccountRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> Account:
    account = await account_service.get(session, auth_subject, id)
    if account is None:
        raise ResourceNotFound()

    return account


@router.post("/accounts", response_model=AccountSchema, status_code=201)
async def create(
    account_create: AccountCreateForWorkspace,
    auth_subject: AccountWrite,
    force_new: bool = Query(
        False, description="Disconnect existing account and create a new one"
    ),
    session: AsyncSession = Depends(get_db_session),
) -> Account:
    workspace = await workspace_service.get(
        session, auth_subject, account_create.workspace_id
    )
    if workspace is None:
        raise ResourceNotFound("Workspace not found")

    account = await account_service.get_or_create_account_for_workspace(
        session,
        workspace=workspace,
        admin=auth_subject.subject,
        account_create=account_create,
        force_new=force_new,
    )

    return account


@router.patch("/accounts/{id}", response_model=AccountSchema)
async def patch(
    id: UUID,
    account_update: AccountUpdate,
    auth_subject: AccountWrite,
    session: AsyncSession = Depends(get_db_session),
) -> Account:
    account = await account_service.get(session, auth_subject, id)
    if account is None:
        raise ResourceNotFound()

    return await account_service.update(session, account, account_update)


# ── Onboarding ──


@router.post(
    "/accounts/{id}/onboarding_link", response_model=AccountLink, status_code=201
)
async def onboarding_link(
    id: UUID,
    auth_subject: AccountWrite,
    return_path: str = Query(...),
    session: AsyncSession = Depends(get_db_session),
) -> AccountLink:
    account = await account_service.get(session, auth_subject, id)
    if account is None:
        raise ResourceNotFound()

    if account.account_type != AccountType.stripe:
        raise ResourceNotFound()

    # Validate return_path to prevent open-redirect attacks
    safe_return_url = get_safe_return_url(return_path)
    link = await account_service.onboarding_link(account, safe_return_url)
    if not link:
        raise InternalServerError("Failed to create link")

    return link


@router.post(
    "/accounts/{id}/dashboard_link", response_model=AccountLink, status_code=201
)
async def dashboard_link(
    id: UUID,
    auth_subject: AccountWrite,
    session: AsyncSession = Depends(get_db_session),
) -> AccountLink:
    account = await account_service.get(session, auth_subject, id)
    if account is None:
        raise ResourceNotFound()

    if not account.is_details_submitted:
        raise ResourceNotFound(
            "Account onboarding is not complete. Please finish setting up your Stripe account first."
        )

    # update stripe account details
    await account_service.sync_to_upstream(session, account)

    link = await account_service.dashboard_link(account)
    if not link:
        raise InternalServerError("Failed to create link")

    return link
