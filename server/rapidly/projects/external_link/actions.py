"""Work-item external link lifecycle: list, get, create, update, delete.

External links point to off-platform resources (Figma, PRs, docs).
Distinct from ``WorkItemRelation``, which links work items to each other.

Mutations require at least the ``member`` project role; workspace-scoped
tokens bypass the gate (implicit admins of every project in their
workspace) via ``require_role``.
"""

from collections.abc import Sequence
from uuid import UUID

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.errors import ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models import ProjectMemberRole, WorkItem, WorkItemLink
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.external_link.ordering import WorkItemLinkSortProperty
from rapidly.projects.external_link.queries import WorkItemLinkRepository
from rapidly.projects.external_link.types import (
    WorkItemLinkCreate,
    WorkItemLinkUpdate,
)
from rapidly.projects.project.access import require_role
from rapidly.projects.project.queries import ProjectRepository
from rapidly.projects.work_item.queries import WorkItemRepository

# ── Reads ──


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> WorkItemLink | None:
    repo = WorkItemLinkRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(WorkItemLink.id == id)
    return await repo.get_one_or_none(stmt)


async def list_for_work_item(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    work_item_id: UUID,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[WorkItemLinkSortProperty]],
) -> tuple[Sequence[WorkItemLink], int]:
    # Confirm the caller can read the work item before listing its links.
    await _readable_work_item(session, auth_subject, work_item_id)

    repo = WorkItemLinkRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject).where(
        WorkItemLink.work_item_id == work_item_id
    )
    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


# ── Writes ──


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    data: WorkItemLinkCreate,
) -> WorkItemLink:
    work_item = await _readable_work_item(session, auth_subject, data.work_item_id)
    await _ensure_member(session, auth_subject, work_item)

    actor_id = (
        auth_subject.subject.id if isinstance(auth_subject.subject, User) else None
    )

    repo = WorkItemLinkRepository.from_session(session)
    link = WorkItemLink(
        work_item_id=data.work_item_id,
        created_by_id=actor_id,
        url=str(data.url),
        title=data.title,
    )
    return await repo.create(link, flush=True)


async def update(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    link: WorkItemLink,
    data: WorkItemLinkUpdate,
) -> WorkItemLink:
    work_item = await _readable_work_item(session, auth_subject, link.work_item_id)
    await _ensure_member(session, auth_subject, work_item)

    update_dict: dict[str, str | None] = {}
    if data.url is not None:
        update_dict["url"] = str(data.url)
    # ``data.title`` is ``None`` both when caller omitted it and when caller
    # set it to null. ``model_dump(exclude_unset=True)`` lets us tell the two
    # apart so a user can clear the title back to NULL.
    raw = data.model_dump(exclude_unset=True)
    if "title" in raw:
        update_dict["title"] = data.title

    if not update_dict:
        return link
    repo = WorkItemLinkRepository.from_session(session)
    return await repo.update(link, update_dict=update_dict)


async def delete(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    link: WorkItemLink,
) -> None:
    work_item = await _readable_work_item(session, auth_subject, link.work_item_id)
    await _ensure_member(session, auth_subject, work_item)
    repo = WorkItemLinkRepository.from_session(session)
    await repo.soft_delete(link)


# ── Helpers ──


async def _readable_work_item(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    work_item_id: UUID,
) -> WorkItem:
    repo = WorkItemRepository.from_session(session)
    work_item = await repo.get_one_or_none(
        repo.get_readable_statement(auth_subject).where(WorkItem.id == work_item_id)
    )
    if work_item is None:
        raise ResourceNotFound("Work item not found.")
    return work_item


async def _ensure_member(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    work_item: WorkItem,
) -> None:
    project_repo = ProjectRepository.from_session(session)
    project = await project_repo.get_one_or_none(
        project_repo.get_readable_statement(auth_subject).where(
            project_repo.model.id == work_item.project_id
        )
    )
    if project is None:
        raise ResourceNotFound("Project not found.")
    await require_role(session, auth_subject, project, minimum=ProjectMemberRole.member)
