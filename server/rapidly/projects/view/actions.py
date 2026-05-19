"""Project-view lifecycle: list, get, create, update, archive, unarchive, delete.

A view is a named filter slice — see ``rapidly/models/project_view.py``.
The action layer enforces:

  - The caller has at least ``member`` on the parent project for any
    mutation (matches cycle / module floors).
  - ``(project_id, name)`` is unique.
  - The owning project is resolved through ``get_readable_statement``
    so workspace isolation holds before any state mutation.
"""

from collections.abc import Sequence
from uuid import UUID

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.core.utils import now_utc
from rapidly.errors import ResourceAlreadyExists, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
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
    name: str | None = None,
    include_archived: bool = False,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[ProjectViewSortProperty]],
) -> tuple[Sequence[ProjectView], int]:
    repo = ProjectViewRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject)
    if project_id is not None:
        statement = statement.where(ProjectView.project_id.in_(project_id))
    if name is not None and name.strip():
        # Escape SQL wildcards — see server/CLAUDE.md "Substring search filter".
        escaped = (
            name.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        statement = statement.where(ProjectView.name.ilike(f"%{escaped}%", escape="\\"))
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

    repo = ProjectViewRepository.from_session(session)
    if await repo.get_by_name(data.project_id, data.name) is not None:
        raise ResourceAlreadyExists(
            f"A view named '{data.name}' already exists in this project."
        )

    owner_id: UUID | None
    if isinstance(auth_subject.subject, User):
        owner_id = auth_subject.subject.id
    else:
        owner_id = None

    view = ProjectView(
        project_id=project.id,
        owner_id=owner_id,
        name=data.name,
        description=data.description,
        filters=data.filters,
    )
    return await repo.create(view, flush=True)


async def update(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    view: ProjectView,
    data: ProjectViewUpdate,
) -> ProjectView:
    await _ensure_member(session, auth_subject, view.project_id)

    update_dict = data.model_dump(exclude_unset=True)
    if not update_dict:
        return view

    if "name" in update_dict:
        repo_check = ProjectViewRepository.from_session(session)
        existing = await repo_check.get_by_name(view.project_id, update_dict["name"])
        if existing is not None and existing.id != view.id:
            raise ResourceAlreadyExists(
                f"A view named '{update_dict['name']}' already exists in this project."
            )

    repo = ProjectViewRepository.from_session(session)
    return await repo.update(view, update_dict=update_dict)


async def archive(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    view: ProjectView,
) -> ProjectView:
    # Same role floor as ``update`` — archiving is reversible and per-row.
    # Passing ``minimum=`` explicitly so tests can pin the floor.
    await _ensure_member(
        session, auth_subject, view.project_id, minimum=ProjectMemberRole.member
    )
    repo = ProjectViewRepository.from_session(session)
    return await repo.update(view, update_dict={"archived_at": now_utc()})


async def unarchive(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    view: ProjectView,
) -> ProjectView:
    await _ensure_member(
        session, auth_subject, view.project_id, minimum=ProjectMemberRole.member
    )
    repo = ProjectViewRepository.from_session(session)
    return await repo.update(view, update_dict={"archived_at": None})


async def delete(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    view: ProjectView,
) -> None:
    await _ensure_member(
        session, auth_subject, view.project_id, minimum=ProjectMemberRole.admin
    )
    repo = ProjectViewRepository.from_session(session)
    await repo.soft_delete(view)


# ── Helpers ──


async def _ensure_member(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    project_id: UUID,
    *,
    minimum: ProjectMemberRole = ProjectMemberRole.member,
) -> Project:
    project_repo = ProjectRepository.from_session(session)
    project = await project_repo.get_one_or_none(
        project_repo.get_readable_statement(auth_subject).where(
            project_repo.model.id == project_id
        )
    )
    if project is None:
        raise ResourceNotFound("Project not found.")
    await require_role(session, auth_subject, project, minimum=minimum)
    return project
