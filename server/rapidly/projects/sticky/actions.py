"""Sticky lifecycle: list, get, create, update, delete.

All operations are scoped to ``owner_id = caller`` by the
repository's readable-statement.  The only extra gate on writes is
checking that the workspace the caller wants to attach a sticky to
is actually one they belong to — keeps a malicious caller from
stashing notes in a workspace they have no other access to.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.errors import BadRequest
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.models import Sticky, WorkspaceMembership
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.sticky.ordering import StickySortProperty
from rapidly.projects.sticky.queries import StickyRepository
from rapidly.projects.sticky.types import StickyCreate, StickyUpdate

# ── Reads ──


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User],
    id: UUID,
) -> Sticky | None:
    repo = StickyRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(Sticky.id == id)
    return await repo.get_one_or_none(stmt)


async def list_mine(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User],
    *,
    workspace_id: UUID | None = None,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[StickySortProperty]],
) -> tuple[Sequence[Sticky], int]:
    repo = StickyRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject)
    if workspace_id is not None:
        statement = statement.where(Sticky.workspace_id == workspace_id)
    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


# ── Writes ──


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    data: StickyCreate,
) -> Sticky:
    await _ensure_workspace_member(session, auth_subject.subject.id, data.workspace_id)

    repo = StickyRepository.from_session(session)
    sticky = Sticky(
        workspace_id=data.workspace_id,
        owner_id=auth_subject.subject.id,
        name=data.name,
        description_json=data.description_json,
        description_html=data.description_html,
        color=data.color,
        sort_order=data.sort_order if data.sort_order is not None else 65535.0,
    )
    return await repo.create(sticky, flush=True)


async def update(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    sticky: Sticky,
    data: StickyUpdate,
) -> Sticky:
    # Readable-statement already restricted to owner, so by the time
    # we have ``sticky`` here we know caller is the owner.
    update_dict = data.model_dump(exclude_unset=True)
    if not update_dict:
        return sticky
    repo = StickyRepository.from_session(session)
    return await repo.update(sticky, update_dict=update_dict)


async def delete(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    sticky: Sticky,
) -> None:
    repo = StickyRepository.from_session(session)
    await repo.soft_delete(sticky)


# ── Helpers ──


async def _ensure_workspace_member(
    session: AsyncSession, user_id: UUID, workspace_id: UUID
) -> None:
    """A user can only stash stickies in workspaces they're a member of.

    Without this guard, a caller could create a sticky against any
    workspace ID — leaking the workspace's existence via the FK
    constraint and using their own user's storage for someone else's
    workspace tree.
    """
    stmt = select(WorkspaceMembership.workspace_id).where(
        WorkspaceMembership.workspace_id == workspace_id,
        WorkspaceMembership.user_id == user_id,
        WorkspaceMembership.deleted_at.is_(None),
    )
    if (await session.execute(stmt)).first() is None:
        raise BadRequest("You are not a member of this workspace.")
