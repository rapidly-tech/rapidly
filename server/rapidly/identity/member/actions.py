"""Member lifecycle: creation, role transitions, ownership guards, and deletion."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams
from rapidly.customers.customer.queries import CustomerRepository
from rapidly.errors import (
    NotPermitted,
    RequestValidationError,
    ResourceNotFound,
    validation_error,
)
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models.customer import Customer, CustomerType
from rapidly.models.member import Member, MemberRole
from rapidly.models.workspace import Workspace as OrgModel
from rapidly.postgres import AsyncReadSession, AsyncSession

from .ordering import MemberSortProperty
from .queries import MemberRepository

_log = structlog.get_logger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────


def _owner_count(members: Sequence[Member]) -> int:
    """Count active owners in a member list."""
    return sum(1 for m in members if m.role == MemberRole.owner)


def _sole_owner_error() -> RequestValidationError:
    return RequestValidationError(
        [
            {
                "type": "value_error",
                "loc": ("body",),
                "msg": "Cannot remove the only owner — transfer ownership first.",
                "input": "",
            }
        ]
    )


# ── Queries ───────────────────────────────────────────────────────


async def list(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    customer_id: UUID | None = None,
    external_customer_id: str | None = None,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[MemberSortProperty]] = (
        (MemberSortProperty.created_at, True),
    ),
) -> tuple[Sequence[Member], int]:
    """List members with pagination and filtering."""
    repo = MemberRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject)
    stmt = repo.apply_list_filters(
        stmt,
        customer_id=customer_id,
        external_customer_id=external_customer_id,
        sorting=sorting,
    )
    return await repo.paginate(stmt, limit=pagination.limit, page=pagination.page)


async def get(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> Member | None:
    """Get a member by ID if the auth subject has access to it."""
    repo = MemberRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(Member.id == id)
    return await repo.get_one_or_none(stmt)


# ── Deletion ──────────────────────────────────────────────────────


async def delete(
    session: AsyncSession,
    member: Member,
) -> Member:
    """Soft-delete *member*, raising if it is the sole owner."""
    repo = MemberRepository.from_session(session)

    if member.role == MemberRole.owner:
        peers = await repo.list_by_customer(session, member.customer_id)
        if _owner_count(peers) <= 1:
            raise _sole_owner_error()

    result = await repo.soft_delete(member)
    _log.info(
        "member.deleted",
        member_id=member.id,
        customer_id=member.customer_id,
        workspace_id=member.workspace_id,
    )
    return result


# ── Owner provisioning ───────────────────────────────────────────


async def create_owner_member(
    session: AsyncSession,
    customer: Customer,
    workspace: OrgModel,
    *,
    owner_email: str | None = None,
    owner_name: str | None = None,
    owner_external_id: str | None = None,
) -> Member | None:
    """Provision an owner member for *customer* if the feature flag is on."""
    if not workspace.feature_settings.get("member_model_enabled", False):
        return None

    repo = MemberRepository.from_session(session)
    email = owner_email or customer.email
    name = owner_name or customer.name
    ext_id = owner_external_id or customer.external_id

    # Use no_autoflush to prevent premature flush of pending parent objects
    # (e.g. a not-yet-committed Customer) when querying for existing members.
    with session.no_autoflush:
        existing = await repo.get_by_customer_and_email(session, customer, email=email)
    if existing:
        return existing

    member = Member(
        customer_id=customer.id,
        workspace_id=workspace.id,
        email=email,
        name=name,
        external_id=ext_id,
        role=MemberRole.owner,
    )

    return await _create_with_conflict_guard(repo, session, member, customer, email)


# ── Batch queries ─────────────────────────────────────────────────


async def list_by_customer(
    session: AsyncReadSession,
    customer_id: UUID,
) -> Sequence[Member]:
    repo = MemberRepository.from_session(session)
    return await repo.list_by_customer(session, customer_id)


async def get_by_customer_and_id(
    session: AsyncReadSession,
    customer_id: UUID,
    member_id: UUID,
) -> Member | None:
    """Get a member by customer ID and member ID."""
    repo = MemberRepository.from_session(session)
    return await repo.get_by_id_and_customer_id(member_id, customer_id)


async def add_to_customer(
    session: AsyncSession,
    customer: Customer,
    *,
    email: str,
    name: str | None = None,
    role: MemberRole = MemberRole.member,
) -> Member:
    """Add a member to *customer*, returning the existing record on conflict."""
    repo = MemberRepository.from_session(session)

    if existing := await repo.get_by_customer_id_and_email(customer.id, email):
        return existing

    member = Member(
        customer_id=customer.id,
        workspace_id=customer.workspace_id,
        email=email,
        name=name,
        role=role,
    )
    created = await repo.create(member, flush=True)
    _log.info(
        "member.added",
        customer_id=customer.id,
        member_id=created.id,
        role=role,
    )
    return created


async def list_by_customers(
    session: AsyncReadSession,
    customer_ids: Sequence[UUID],
) -> Sequence[Member]:
    """Batch-load members for multiple customers (avoids N+1)."""
    repo = MemberRepository.from_session(session)
    return await repo.list_by_customers(session, customer_ids)


async def find_case_insensitive_email_duplicates(
    session: AsyncReadSession,
) -> Sequence[tuple[UUID, str, int]]:
    """Report active (customer_id, lower(email)) groups with >1
    members — operators dedupe these before the case-insensitive
    unique constraint migration (queued) can land.

    Returns ``(customer_id, lower_email, count)`` tuples ordered
    by count desc. Empty list = no duplicates = constraint
    migration is safe to apply.
    """
    repo = MemberRepository.from_session(session)
    return await repo.find_case_insensitive_email_duplicates()


async def auto_dedupe_case_insensitive_email_duplicates(
    session: AsyncSession,
) -> int:
    """Soft-delete duplicate Member rows that would block the
    case-insensitive unique constraint migration.

    Policy (per ``(customer_id, lower(email))`` group):

      1. Survivor = the row with the highest role (owner >
         billing_manager > member). Preserves the strongest
         capability across the merge.
      2. Tie-break = earliest ``created_at``. The "original"
         registration wins.
      3. Losers = all other rows in the group → soft-deleted.

    DOES NOT touch ``external_id`` / ``oauth_accounts`` on the
    survivor — those have their own unique constraints and
    merging could create new conflicts (and operators may want
    review on identity-merge decisions anyway).

    Returns the total number of LOSER rows soft-deleted. Run
    ``find_case_insensitive_email_duplicates`` after this to
    confirm zero remain.

    Idempotent — re-running on a deduped table is a no-op
    (the finder returns nothing → this returns 0).
    """
    repo = MemberRepository.from_session(session)
    total_deleted = 0
    duplicates = await repo.find_case_insensitive_email_duplicates()
    for customer_id, lower_email, _ in duplicates:
        members = await repo.list_duplicates_for_dedupe(customer_id, lower_email)
        if len(members) < 2:
            # Race: another caller already deduped this group.
            continue
        survivor = members[0]
        losers = members[1:]
        for loser in losers:
            await repo.soft_delete(loser)
            total_deleted += 1
        _log.info(
            "member.auto_deduped",
            customer_id=customer_id,
            lower_email=lower_email,
            survivor_id=survivor.id,
            losers=len(losers),
        )
    return total_deleted


# ── Authenticated creation ───────────────────────────────────────


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    customer_id: UUID,
    email: str,
    name: str | None = None,
    external_id: str | None = None,
    role: MemberRole = MemberRole.member,
) -> Member:
    """Create a member, enforcing feature flags and individual-customer limits."""
    customer = await _resolve_customer(session, auth_subject, customer_id)
    _guard_feature_enabled(customer.workspace)
    repo = MemberRepository.from_session(session)

    await _guard_individual_limit(repo, session, customer, customer_id)

    if existing := await repo.get_by_customer_and_email(session, customer, email=email):
        return existing

    member = Member(
        customer_id=customer_id,
        workspace_id=customer.workspace_id,
        email=email,
        name=name,
        external_id=external_id,
        role=role,
    )
    return await _create_with_conflict_guard(repo, session, member, customer, email)


# ── Update ──────────────────────────────────────────────────────


async def update(
    session: AsyncSession,
    member: Member,
    *,
    name: str | None = None,
    role: MemberRole | None = None,
) -> Member:
    """Update mutable member fields, guarding the single-owner invariant."""
    repo = MemberRepository.from_session(session)

    if role is not None and member.role != role:
        _guard_role_transition(
            member, role, await repo.list_by_customer(session, member.customer_id)
        )

    changes: dict[str, Any] = {}
    if name is not None:
        changes["name"] = name
    if role is not None:
        changes["role"] = role

    if not changes:
        return member

    updated = await repo.update(member, update_dict=changes)
    _log.info(
        "member.updated",
        member_id=member.id,
        fields=[*changes.keys()],
    )
    return updated


async def transfer_ownership(
    session: AsyncSession,
    current_owner: Member,
    new_owner: Member,
) -> Member:
    """Transfer ownership from one member to another atomically.

    Bypasses the single-owner guard since we're swapping roles.
    """
    repo = MemberRepository.from_session(session)

    # Promote new owner first, then demote current owner
    await repo.update(new_owner, update_dict={"role": MemberRole.owner})
    await repo.update(current_owner, update_dict={"role": MemberRole.billing_manager})

    _log.info(
        "member.ownership_transferred",
        from_member_id=current_owner.id,
        to_member_id=new_owner.id,
    )
    return new_owner


# ── Private helpers ───────────────────────────────────────────────


def _guard_role_transition(
    member: Member, target: MemberRole, peers: Sequence[Member]
) -> None:
    owners = _owner_count(peers)
    losing = member.role == MemberRole.owner and target != MemberRole.owner
    gaining = target == MemberRole.owner and member.role != MemberRole.owner
    if (losing and owners <= 1) or (gaining and owners >= 1):
        raise RequestValidationError(
            [validation_error("role", "Customer must have exactly one owner.", target)]
        )


def _guard_feature_enabled(org: OrgModel) -> None:
    if not org.feature_settings.get("member_model_enabled", False):
        raise NotPermitted("Member management is not enabled for this workspace")


async def _resolve_customer(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    customer_id: UUID,
) -> Customer:
    cust_repo = CustomerRepository.from_session(session)
    customer = await cust_repo.get_readable_by_id(
        auth_subject, customer_id, options=(joinedload(Customer.workspace),)
    )
    if customer is None:
        raise ResourceNotFound("Customer not found")
    return customer


async def _guard_individual_limit(
    repo: MemberRepository,
    session: AsyncSession,
    customer: Customer,
    customer_id: UUID,
) -> None:
    ctype = customer.type or CustomerType.individual
    if ctype == CustomerType.individual:
        existing = await repo.list_by_customer(session, customer_id)
        active = [m for m in existing if m.deleted_at is None]
        if len(active) >= 1:
            raise NotPermitted(
                "Individual customers can only have one member. "
                "Upgrade to a team customer to add more."
            )


async def _create_with_conflict_guard(
    repo: MemberRepository,
    session: AsyncSession,
    member: Member,
    customer: Customer,
    email: str,
) -> Member:
    """Attempt insert; on unique-constraint conflict, return existing row."""
    try:
        created = await repo.create(member, flush=True)
        _log.info(
            "member.created",
            customer_id=customer.id,
            member_id=created.id,
            role=member.role,
        )
        return created
    except IntegrityError:
        if existing := await repo.get_by_customer_and_email(
            session, customer, email=email
        ):
            return existing
        raise
