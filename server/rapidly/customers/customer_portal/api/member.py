"""Customer-portal member routes: profile, events, and wallet access.

Exposes member-scoped endpoints within the customer portal for viewing
member details, associated events, wallet balances, and share
entitlements.
"""

from uuid import UUID

import structlog
from fastapi import Depends

from rapidly.errors import (
    NotPermitted,
    RequestValidationError,
    ResourceNotFound,
    validation_error,
)
from rapidly.identity.auth.models import is_member_principal
from rapidly.identity.member import actions as member_service
from rapidly.models.customer import CustomerType
from rapidly.models.member import Member, MemberRole
from rapidly.openapi import APITag
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.routing import APIRouter

from .. import permissions as auth
from ..types.member import (
    CustomerPortalMember,
    CustomerPortalMemberCreate,
    CustomerPortalMemberUpdate,
)
from ..utils import get_customer

_log = structlog.get_logger()

router = APIRouter(prefix="/members", tags=["members", APITag.public])


def _require_team_customer(auth_subject: auth.CustomerPortalBillingManager) -> None:
    """Validate that the customer is a team customer."""
    customer = get_customer(auth_subject)
    if customer.type != CustomerType.team:
        raise NotPermitted(
            "Member management is only available for team customers. "
            "Purchase a seat-based share to enable team features."
        )


# ── List ──


@router.get(
    "",
    summary="List Members",
    response_model=list[CustomerPortalMember],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Not permitted - requires owner or billing manager role"},
    },
)
async def list_members(
    auth_subject: auth.CustomerPortalBillingManager,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> list[Member]:
    """
    List all members of the customer's team.

    Only available to owners and billing managers of team customers.
    """
    _require_team_customer(auth_subject)
    customer = get_customer(auth_subject)

    members = await member_service.list_by_customer(session, customer.id)

    _log.info(
        "customer_portal.members.list",
        customer_id=customer.id,
        member_count=len(members),
        actor_member_id=auth_subject.subject.id
        if is_member_principal(auth_subject)
        else None,
    )

    return list(members)


# ── Add ──


@router.post(
    "",
    summary="Add Member",
    response_model=CustomerPortalMember,
    status_code=201,
    responses={
        201: {"description": "Member added."},
        400: {"description": "Invalid request or member already exists."},
        401: {"description": "Authentication required"},
        403: {"description": "Not permitted - requires owner or billing manager role"},
    },
)
async def add_member(
    member_create: CustomerPortalMemberCreate,
    auth_subject: auth.CustomerPortalBillingManager,
    session: AsyncSession = Depends(get_db_session),
) -> Member:
    """
    Add a new member to the customer's team.

    Only available to owners and billing managers of team customers.

    Rules:
    - Cannot add a member with the owner role (there must be exactly one owner)
    - If a member with this email already exists, the existing member is returned
    """
    _require_team_customer(auth_subject)
    customer = get_customer(auth_subject)

    # Prevent adding a new owner - there must be exactly one
    if member_create.role == MemberRole.owner:
        raise RequestValidationError(
            [
                validation_error(
                    "role",
                    "Cannot add a member as owner. There must be exactly one owner.",
                    member_create.role,
                )
            ]
        )

    return await member_service.add_to_customer(
        session,
        customer,
        email=member_create.email,
        name=member_create.name,
        role=member_create.role,
    )


# ── Update ──


@router.patch(
    "/{id}",
    summary="Update Member",
    response_model=CustomerPortalMember,
    responses={
        200: {"description": "Member updated."},
        400: {"description": "Invalid role change."},
        401: {"description": "Authentication required"},
        403: {"description": "Not permitted - requires owner or billing manager role"},
        404: {"description": "Member not found."},
    },
)
async def update_member(
    id: UUID,
    member_update: CustomerPortalMemberUpdate,
    auth_subject: auth.CustomerPortalBillingManager,
    session: AsyncSession = Depends(get_db_session),
) -> Member:
    """
    Update a member's role.

    Only available to owners and billing managers of team customers.

    Rules:
    - Cannot modify your own role (to prevent self-demotion)
    - Customer must have exactly one owner at all times
    """
    _require_team_customer(auth_subject)
    customer = get_customer(auth_subject)
    actor_member = auth_subject.subject

    # Fetch the member
    member = await member_service.get_by_customer_and_id(session, customer.id, id)
    if member is None:
        raise ResourceNotFound("Member not found")

    # If no role provided, return member unchanged
    if member_update.role is None:
        return member

    # Prevent self-modification
    if member.id == actor_member.id:
        raise RequestValidationError(
            [
                validation_error(
                    "id", "You cannot modify your own role.", str(id), loc_prefix="path"
                )
            ]
        )

    # Handle ownership transfer: only the current owner can promote someone to owner
    if member_update.role == MemberRole.owner:
        if actor_member.role != MemberRole.owner:
            raise RequestValidationError(
                [
                    validation_error(
                        "role",
                        "Only the owner can transfer ownership.",
                        member_update.role,
                    )
                ]
            )
        # Transfer ownership atomically: promote target, demote self
        return await member_service.transfer_ownership(session, actor_member, member)

    return await member_service.update(session, member, role=member_update.role)


# ── Remove ──


@router.delete(
    "/{id}",
    status_code=204,
    summary="Remove Member",
    responses={
        204: {"description": "Member removed."},
        400: {"description": "Cannot remove the only owner."},
        401: {"description": "Authentication required"},
        403: {"description": "Not permitted - requires owner or billing manager role"},
        404: {"description": "Member not found."},
    },
)
async def remove_member(
    id: UUID,
    auth_subject: auth.CustomerPortalBillingManager,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Remove a member from the team.

    Only available to owners and billing managers of team customers.

    Rules:
    - Cannot remove yourself
    - Cannot remove the only owner
    """
    _require_team_customer(auth_subject)
    customer = get_customer(auth_subject)
    actor_member = auth_subject.subject

    # Fetch the member
    member = await member_service.get_by_customer_and_id(session, customer.id, id)
    if member is None:
        raise ResourceNotFound("Member not found")

    # Prevent self-removal
    if member.id == actor_member.id:
        raise RequestValidationError(
            [
                validation_error(
                    "id",
                    "You cannot remove yourself from the team.",
                    str(id),
                    loc_prefix="path",
                )
            ]
        )

    # delete() handles the "cannot delete only owner" validation
    await member_service.delete(session, member)
