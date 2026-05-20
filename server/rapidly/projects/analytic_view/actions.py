"""Analytic-view lifecycle: list, get, create, update, delete.

Writes are gated by workspace membership and (when ``project_id``
is set) project membership.  The ``member`` floor on the project
matches peer submodules; saving a dashboard is treated as a
modify-your-shared-tools action, not an admin one.

The actual analytics queries live in the analytics domain — this
submodule is just the *saved configuration* layer.  The frontend
re-renders the chart by reposting the ``query`` to the analytics
endpoints each time it opens the dashboard.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.errors import BadRequest, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models import (
    AnalyticView,
    Project,
    ProjectMemberRole,
    WorkspaceMembership,
)
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.analytic_view.ordering import AnalyticViewSortProperty
from rapidly.projects.analytic_view.queries import AnalyticViewRepository
from rapidly.projects.analytic_view.types import (
    AnalyticViewCreate,
    AnalyticViewUpdate,
)
from rapidly.projects.project.access import require_role
from rapidly.projects.project.queries import ProjectRepository

# ── Reads ──


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> AnalyticView | None:
    repo = AnalyticViewRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(AnalyticView.id == id)
    return await repo.get_one_or_none(stmt)


async def list_views(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    workspace_id: UUID | None = None,
    project_id: UUID | None = None,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[AnalyticViewSortProperty]],
) -> tuple[Sequence[AnalyticView], int]:
    repo = AnalyticViewRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject)
    if workspace_id is not None:
        statement = statement.where(AnalyticView.workspace_id == workspace_id)
    if project_id is not None:
        statement = statement.where(AnalyticView.project_id == project_id)
    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


# ── Writes ──


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    data: AnalyticViewCreate,
) -> AnalyticView:
    await _ensure_workspace_access(session, auth_subject, data.workspace_id)

    if data.project_id is not None:
        project = await _ensure_member(session, auth_subject, data.project_id)
        # Project must live in the same workspace as the view's owner.
        if project.workspace_id != data.workspace_id:
            raise BadRequest("Project does not belong to this workspace.")

    created_by_id = (
        auth_subject.subject.id if isinstance(auth_subject.subject, User) else None
    )
    record = AnalyticView(
        workspace_id=data.workspace_id,
        project_id=data.project_id,
        created_by_id=created_by_id,
        name=data.name,
        description=data.description,
        query=data.query,
    )
    repo = AnalyticViewRepository.from_session(session)
    return await repo.create(record, flush=True)


async def update(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    view: AnalyticView,
    data: AnalyticViewUpdate,
) -> AnalyticView:
    await _ensure_workspace_access(session, auth_subject, view.workspace_id)
    if view.project_id is not None:
        await _ensure_member(session, auth_subject, view.project_id)

    update_dict = data.model_dump(exclude_unset=True)
    if not update_dict:
        return view
    repo = AnalyticViewRepository.from_session(session)
    return await repo.update(view, update_dict=update_dict)


async def delete(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    view: AnalyticView,
) -> None:
    await _ensure_workspace_access(session, auth_subject, view.workspace_id)
    if view.project_id is not None:
        await _ensure_member(session, auth_subject, view.project_id)
    repo = AnalyticViewRepository.from_session(session)
    await repo.soft_delete(view)


# ── Helpers ──


async def _ensure_workspace_access(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    workspace_id: UUID,
) -> None:
    """Verify the caller can read the workspace.

    Workspace-scoped tokens must belong to *this* workspace.  Users
    must be a workspace member.  Without this guard, a caller could
    create a dashboard against any workspace ID — leaking existence
    via FK violation timing or stashing data against someone else's
    workspace tree.
    """
    if isinstance(auth_subject.subject, Workspace):
        if auth_subject.subject.id != workspace_id:
            raise ResourceNotFound("Workspace not found.")
        return

    stmt = select(WorkspaceMembership.workspace_id).where(
        WorkspaceMembership.workspace_id == workspace_id,
        WorkspaceMembership.user_id == auth_subject.subject.id,
        WorkspaceMembership.deleted_at.is_(None),
    )
    if (await session.execute(stmt)).first() is None:
        raise ResourceNotFound("Workspace not found.")


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
