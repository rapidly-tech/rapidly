"""Work-item-type lifecycle: list, get, create, update, delete.

Creating, updating, or deleting a type requires the ``admin`` project
role — types are part of the project's schema and shouldn't be
churnable by every member.  Listing follows the standard
work-item readability filter.

``is_default`` is tracked but the project's "current default" is
*not* enforced as unique here — multiple rows can carry the flag
without breaking referential integrity, and the frontend picks
whichever the highest sort_order one for "new work item" defaults.
Adding a single-default invariant later is a follow-up.
"""

from collections.abc import Sequence
from uuid import UUID

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.errors import ResourceAlreadyExists, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models import Project, ProjectMemberRole, WorkItemType
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.project.access import require_role
from rapidly.projects.project.queries import ProjectRepository
from rapidly.projects.work_item_type.ordering import WorkItemTypeSortProperty
from rapidly.projects.work_item_type.queries import WorkItemTypeRepository
from rapidly.projects.work_item_type.types import (
    WorkItemTypeCreate,
    WorkItemTypeUpdate,
)

# ── Reads ──


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> WorkItemType | None:
    repo = WorkItemTypeRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(WorkItemType.id == id)
    return await repo.get_one_or_none(stmt)


async def list_for_project(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    project_id: Sequence[UUID] | None = None,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[WorkItemTypeSortProperty]],
) -> tuple[Sequence[WorkItemType], int]:
    repo = WorkItemTypeRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject)
    if project_id is not None:
        statement = statement.where(WorkItemType.project_id.in_(project_id))
    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


# ── Writes ──


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    data: WorkItemTypeCreate,
) -> WorkItemType:
    project = await _ensure_admin(session, auth_subject, data.project_id)

    repo = WorkItemTypeRepository.from_session(session)
    if await repo.get_by_project_and_name(project.id, data.name) is not None:
        raise ResourceAlreadyExists(
            f"A work-item type named '{data.name}' already exists in this project."
        )

    work_item_type = WorkItemType(
        project_id=project.id,
        name=data.name,
        description=data.description,
        logo_props=data.logo_props,
        is_epic=data.is_epic,
        is_default=data.is_default,
        is_active=data.is_active,
        sort_order=data.sort_order if data.sort_order is not None else 65535.0,
    )
    return await repo.create(work_item_type, flush=True)


async def update(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    work_item_type: WorkItemType,
    data: WorkItemTypeUpdate,
) -> WorkItemType:
    await _ensure_admin(session, auth_subject, work_item_type.project_id)

    update_dict = data.model_dump(exclude_unset=True)
    if "name" in update_dict and update_dict["name"] != work_item_type.name:
        repo_ = WorkItemTypeRepository.from_session(session)
        if (
            await repo_.get_by_project_and_name(
                work_item_type.project_id, update_dict["name"]
            )
            is not None
        ):
            raise ResourceAlreadyExists(
                f"A work-item type named '{update_dict['name']}' already exists "
                "in this project."
            )

    if not update_dict:
        return work_item_type
    repo = WorkItemTypeRepository.from_session(session)
    return await repo.update(work_item_type, update_dict=update_dict)


async def delete(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    work_item_type: WorkItemType,
) -> None:
    await _ensure_admin(session, auth_subject, work_item_type.project_id)
    repo = WorkItemTypeRepository.from_session(session)
    await repo.soft_delete(work_item_type)


# ── Helpers ──


async def _ensure_admin(
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
    await require_role(session, auth_subject, project, minimum=ProjectMemberRole.admin)
    return project
