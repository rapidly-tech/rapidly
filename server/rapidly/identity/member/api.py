"""Member HTTP routes: CRUD within a workspace context.

Provides endpoints for listing, creating, updating, and deleting
members, scoped to the caller's workspace.
"""

from uuid import UUID

from fastapi import Depends, Query

from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.customers.customer.types.customer import ExternalCustomerID
from rapidly.errors import ResourceNotFound
from rapidly.openapi import APITag
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.routing import APIRouter

from . import actions as member_service
from . import ordering
from . import permissions as auth
from .types import Member, MemberCreate, MemberUpdate

router = APIRouter(
    prefix="/members",
    tags=["members", APITag.public, APITag.mcp],
)

MemberNotFound = {
    "description": "Member not found.",
    "model": ResourceNotFound.schema(),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_customer_id(raw: str | None) -> UUID | None:
    """Validate and convert an optional customer-id query parameter."""
    if raw is None:
        return None
    try:
        return UUID(raw)
    except ValueError:
        raise ResourceNotFound("Invalid customer ID format")


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@router.get(
    "/",
    summary="List Members",
    response_model=PaginatedList[Member],
)
async def list_members(
    auth_subject: auth.MemberRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.ListSorting,
    customer_id: str | None = Query(None, description="Filter by customer ID."),
    external_customer_id: ExternalCustomerID | None = Query(
        None, description="Filter by customer external ID."
    ),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> PaginatedList[Member]:
    """List members with optional customer ID filter."""
    results, count = await member_service.list(
        session,
        auth_subject,
        customer_id=_parse_customer_id(customer_id),
        external_customer_id=external_customer_id,
        pagination=pagination,
        sorting=sorting,
    )

    return PaginatedList.from_paginated_results(
        [Member.model_validate(m) for m in results],
        count,
        pagination,
    )


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=Member,
    status_code=201,
    summary="Create Member",
    responses={
        201: {"description": "Member created."},
        403: {"description": "Not permitted to add members."},
        404: MemberNotFound,
    },
)
async def create_member(
    member_create: MemberCreate,
    auth_subject: auth.MemberWrite,
    session: AsyncSession = Depends(get_db_session),
) -> Member:
    """
    Create a new member for a customer.

    Only B2B customers with the member management feature enabled can add members.
    The authenticated user or workspace must have access to the customer's workspace.
    """
    result = await member_service.create(
        session,
        auth_subject,
        customer_id=member_create.customer_id,
        email=member_create.email,
        name=member_create.name,
        external_id=member_create.external_id,
        role=member_create.role,
    )
    return Member.model_validate(result)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


@router.get(
    "/{id}",
    summary="Get Member",
    response_model=Member,
    responses={200: {"description": "Member retrieved."}, 404: MemberNotFound},
)
async def get_member(
    id: UUID,
    auth_subject: auth.MemberRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> Member:
    """
    Get a member by ID.

    The authenticated user or workspace must have access to the member's workspace.
    """
    member = await member_service.get(session, auth_subject, id)
    if member is None:
        raise ResourceNotFound("Member not found")
    return Member.model_validate(member)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


@router.patch(
    "/{id}",
    summary="Update Member",
    response_model=Member,
    responses={200: {"description": "Member updated."}, 404: MemberNotFound},
)
async def update_member(
    id: UUID,
    member_update: MemberUpdate,
    auth_subject: auth.MemberWrite,
    session: AsyncSession = Depends(get_db_session),
) -> Member:
    """
    Update a member.

    Only name and role can be updated.
    The authenticated user or workspace must have access to the member's workspace.
    """
    member = await member_service.get(session, auth_subject, id)
    if member is None:
        raise ResourceNotFound("Member not found")

    updated = await member_service.update(
        session,
        member,
        name=member_update.name,
        role=member_update.role,
    )
    return Member.model_validate(updated)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@router.delete(
    "/{id}",
    status_code=204,
    summary="Delete Member",
    responses={204: {"description": "Member deleted."}, 404: MemberNotFound},
)
async def delete_member(
    id: UUID,
    auth_subject: auth.MemberWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Delete a member.

    The authenticated user or workspace must have access to the member's workspace.
    """
    member = await member_service.get(session, auth_subject, id)
    if member is None:
        raise ResourceNotFound("Member not found")
    await member_service.delete(session, member)
