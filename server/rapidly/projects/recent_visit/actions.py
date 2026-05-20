"""Recent-visit lifecycle: list, record (upsert), delete-one, clear.

Workspace-membership pre-check on ``record`` keeps callers from
probing workspace IDs by recording visits against them.

The dedicated ``visited_at`` column is intentionally separate from
``created_at`` / ``modified_at`` — those are auditing timestamps,
while ``visited_at`` is the product-visible "last touched" that the
client orders by.  Bumping ``modified_at`` on every visit would
muddy the audit trail.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from rapidly.core.pagination import PaginationParams, paginate
from rapidly.core.utils import now_utc
from rapidly.errors import BadRequest
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.models import (
    RecentVisit,
    RecentVisitEntityType,
    WorkspaceMembership,
)
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.recent_visit.queries import RecentVisitRepository
from rapidly.projects.recent_visit.types import RecentVisitRecord

# ── Reads ──


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User],
    id: UUID,
) -> RecentVisit | None:
    repo = RecentVisitRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(RecentVisit.id == id)
    return await repo.get_one_or_none(stmt)


async def list_mine(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User],
    *,
    workspace_id: UUID | None = None,
    entity_type: RecentVisitEntityType | None = None,
    pagination: PaginationParams,
) -> tuple[Sequence[RecentVisit], int]:
    repo = RecentVisitRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject)
    if workspace_id is not None:
        statement = statement.where(RecentVisit.workspace_id == workspace_id)
    if entity_type is not None:
        statement = statement.where(RecentVisit.entity_type == entity_type)
    # Always sort by visited_at desc — recents have no other useful order.
    statement = statement.order_by(RecentVisit.visited_at.desc())
    return await paginate(session, statement, pagination=pagination)


# ── Writes ──


async def record(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    data: RecentVisitRecord,
) -> RecentVisit:
    """Upsert: bump ``visited_at`` if the triplet exists, otherwise insert."""
    await _ensure_workspace_member(session, auth_subject.subject.id, data.workspace_id)

    repo = RecentVisitRepository.from_session(session)
    existing = await repo.get_for_triplet(
        auth_subject.subject.id, data.entity_type, data.entity_id
    )
    visited = now_utc()

    if existing is not None:
        return await repo.update(existing, update_dict={"visited_at": visited})

    record = RecentVisit(
        user_id=auth_subject.subject.id,
        workspace_id=data.workspace_id,
        entity_type=data.entity_type,
        entity_id=data.entity_id,
        visited_at=visited,
    )
    return await repo.create(record, flush=True)


async def delete(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    visit: RecentVisit,
) -> None:
    repo = RecentVisitRepository.from_session(session)
    await repo.soft_delete(visit)


# ── Helpers ──


async def _ensure_workspace_member(
    session: AsyncSession, user_id: UUID, workspace_id: UUID
) -> None:
    stmt = select(WorkspaceMembership.workspace_id).where(
        WorkspaceMembership.workspace_id == workspace_id,
        WorkspaceMembership.user_id == user_id,
        WorkspaceMembership.deleted_at.is_(None),
    )
    if (await session.execute(stmt)).first() is None:
        raise BadRequest("You are not a member of this workspace.")
