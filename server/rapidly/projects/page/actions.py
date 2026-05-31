"""Page lifecycle: list, get, create, update, delete.

Guards:
- The parent page (if specified) must live in the same project.
- A page locked via ``is_locked`` rejects updates from non-admins until
  unlocked.
- Owner-only mutations: only the page's owner or a project admin can
  edit / delete a private page (mirrors comments).
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.errors import (
    BadRequest,
    NotPermitted,
    ResourceAlreadyExists,
    ResourceNotFound,
)
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    Workspace,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import (
    Project,
    ProjectMemberRole,
    ProjectPage,
)
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.page.ordering import ProjectPageSortProperty
from rapidly.projects.page.queries import ProjectPageRepository
from rapidly.projects.page.types import ProjectPageCreate, ProjectPageUpdate
from rapidly.projects.project.access import require_role
from rapidly.projects.project.queries import ProjectRepository

# ── Reads ──


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> ProjectPage | None:
    repo = ProjectPageRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(ProjectPage.id == id)
    return await repo.get_one_or_none(stmt)


async def list_for_project(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    project_id: Sequence[UUID] | None = None,
    parent_id: UUID | None = None,
    include_archived: bool = False,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[ProjectPageSortProperty]],
) -> tuple[Sequence[ProjectPage], int]:
    repo = ProjectPageRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject)
    if project_id is not None:
        statement = statement.where(ProjectPage.project_id.in_(project_id))
    if parent_id is not None:
        statement = statement.where(ProjectPage.parent_id == parent_id)
    if not include_archived:
        statement = statement.where(ProjectPage.archived_at.is_(None))
    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


# ── Writes ──


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    data: ProjectPageCreate,
) -> ProjectPage:
    project = await _ensure_member(session, auth_subject, data.project_id)

    if data.parent_id is not None:
        await _verify_parent(session, project.id, data.parent_id)

    repo = ProjectPageRepository.from_session(session)
    if await repo.get_by_slug(project.id, data.slug) is not None:
        raise ResourceAlreadyExists(
            f"A page with slug '{data.slug}' already exists in this project."
        )

    owner_id = auth_subject.subject.id if is_user_principal(auth_subject) else None
    page = ProjectPage(
        project_id=project.id,
        owner_id=owner_id,
        parent_id=data.parent_id,
        name=data.name,
        slug=data.slug,
        description_json=data.description_json,
        description_html=data.description_html,
        access=data.access,
    )
    return await repo.create(page, flush=True)


async def update(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    page: ProjectPage,
    data: ProjectPageUpdate,
) -> ProjectPage:
    project = await _ensure_member(session, auth_subject, page.project_id)

    # Locked pages reject mutations from non-admins; an admin can still
    # toggle ``is_locked`` itself to unlock.
    if page.is_locked:
        await require_role(
            session, auth_subject, project, minimum=ProjectMemberRole.admin
        )

    # Private-page edits remain author-only unless the caller is admin.
    await _require_author_or_admin(session, auth_subject, page, project)

    if data.parent_id is not None:
        if data.parent_id == page.id:
            raise BadRequest("A page cannot be its own parent.")
        await _verify_parent(session, project.id, data.parent_id)

    if data.slug is not None and data.slug != page.slug:
        repo_ = ProjectPageRepository.from_session(session)
        if await repo_.get_by_slug(project.id, data.slug) is not None:
            raise ResourceAlreadyExists(
                f"A page with slug '{data.slug}' already exists in this project."
            )

    repo = ProjectPageRepository.from_session(session)
    update_dict = data.model_dump(exclude_unset=True)
    if not update_dict:
        return page
    return await repo.update(page, update_dict=update_dict)


async def delete(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    page: ProjectPage,
) -> None:
    project = await _ensure_member(session, auth_subject, page.project_id)
    await _require_author_or_admin(session, auth_subject, page, project)
    repo = ProjectPageRepository.from_session(session)
    await repo.soft_delete(page)


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


async def _verify_parent(
    session: AsyncSession, project_id: UUID, parent_id: UUID
) -> None:
    stmt = select(ProjectPage.id).where(
        ProjectPage.id == parent_id,
        ProjectPage.project_id == project_id,
        ProjectPage.deleted_at.is_(None),
    )
    if (await session.execute(stmt)).scalar_one_or_none() is None:
        raise BadRequest("Parent page does not belong to this project.")


async def _require_author_or_admin(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    page: ProjectPage,
    project: Project,
) -> None:
    if is_workspace_principal(auth_subject):
        # Workspace tokens are admins in their own workspace.
        return
    if not is_user_principal(auth_subject):
        raise NotPermitted("Unsupported auth subject.")
    if page.owner_id is not None and auth_subject.subject.id == page.owner_id:
        return
    await require_role(session, auth_subject, project, minimum=ProjectMemberRole.admin)
