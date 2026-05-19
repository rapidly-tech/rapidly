"""Project saved-view lifecycle: list, get, create, update, delete, archive.

Saved views are filter+display presets users save and reuse on a
project's work-item list.  Any project member can create their own;
the owner and project admins can mutate.  ``is_locked`` blocks
non-admin updates entirely.
"""

from collections.abc import Sequence
from uuid import UUID

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.core.utils import now_utc
from rapidly.errors import NotPermitted, ResourceNotFound
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    Workspace,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import Project, ProjectMemberRole, ProjectView
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.project.access import require_role
from rapidly.projects.project.queries import ProjectRepository
from rapidly.projects.view.ordering import ProjectViewSortProperty
from rapidly.projects.view.queries import ProjectViewRepository
from rapidly.projects.view.types import ProjectViewCreate, ProjectViewUpdate

# ── Reads ──


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> ProjectView | None:
    repo = ProjectViewRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(ProjectView.id == id)
    return await repo.get_one_or_none(stmt)


async def list_for_project(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    project_id: Sequence[UUID] | None = None,
    include_archived: bool = False,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[ProjectViewSortProperty]],
) -> tuple[Sequence[ProjectView], int]:
    repo = ProjectViewRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject)
    if project_id is not None:
        statement = statement.where(ProjectView.project_id.in_(project_id))
    if not include_archived:
        statement = statement.where(ProjectView.archived_at.is_(None))
    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


# ── Writes ──


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    data: ProjectViewCreate,
) -> ProjectView:
    project = await _ensure_member(session, auth_subject, data.project_id)

    owner_id = auth_subject.subject.id if is_user_principal(auth_subject) else None
    view = ProjectView(
        project_id=project.id,
        owner_id=owner_id,
        name=data.name,
        description=data.description,
        filters=data.filters,
        display_filters=data.display_filters,
        display_properties=data.display_properties,
        access=data.access,
    )
    repo = ProjectViewRepository.from_session(session)
    return await repo.create(view, flush=True)


async def update(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    view: ProjectView,
    data: ProjectViewUpdate,
) -> ProjectView:
    project = await _ensure_member(session, auth_subject, view.project_id)

    # Locked views reject mutations from non-admins; an admin can still
    # toggle ``is_locked`` itself to unlock.
    if view.is_locked:
        await require_role(
            session, auth_subject, project, minimum=ProjectMemberRole.admin
        )

    await _require_owner_or_admin(session, auth_subject, view, project)

    update_dict = data.model_dump(exclude_unset=True)
    if not update_dict:
        return view
    repo = ProjectViewRepository.from_session(session)
    return await repo.update(view, update_dict=update_dict)


async def delete(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    view: ProjectView,
) -> None:
    project = await _ensure_member(session, auth_subject, view.project_id)
    await _require_owner_or_admin(session, auth_subject, view, project)
    repo = ProjectViewRepository.from_session(session)
    await repo.soft_delete(view)


async def archive(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    view: ProjectView,
) -> ProjectView:
    project = await _ensure_member(session, auth_subject, view.project_id)
    await _require_owner_or_admin(session, auth_subject, view, project)
    repo = ProjectViewRepository.from_session(session)
    return await repo.update(view, update_dict={"archived_at": now_utc()})


async def unarchive(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    view: ProjectView,
) -> ProjectView:
    project = await _ensure_member(session, auth_subject, view.project_id)
    await _require_owner_or_admin(session, auth_subject, view, project)
    repo = ProjectViewRepository.from_session(session)
    return await repo.update(view, update_dict={"archived_at": None})


# ── Helpers ──


async def _ensure_member(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    project_id: UUID,
) -> Project:
    project_repo = ProjectRepository.from_session(session)
    project = await project_repo.get_one_or_none(
        project_repo.get_readable_statement(auth_subject).where(
            project_repo.model.id == project_id
        )
    )
    if project is None:
        raise ResourceNotFound("Project not found.")
    await require_role(session, auth_subject, project, minimum=ProjectMemberRole.member)
    return project


async def _require_owner_or_admin(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    view: ProjectView,
    project: Project,
) -> None:
    if is_workspace_principal(auth_subject):
        # Workspace tokens are admins in their own workspace.
        return
    if not is_user_principal(auth_subject):
        raise NotPermitted("Unsupported auth subject.")
    if view.owner_id is not None and auth_subject.subject.id == view.owner_id:
        return
    await require_role(session, auth_subject, project, minimum=ProjectMemberRole.admin)
