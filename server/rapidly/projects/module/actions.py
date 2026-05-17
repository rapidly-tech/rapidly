"""Module lifecycle: list, get, create, update, delete + work-item membership."""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.core.utils import now_utc
from rapidly.errors import (
    BadRequest,
    ResourceAlreadyExists,
    ResourceNotFound,
)
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models import (
    Project,
    ProjectMemberRole,
    ProjectModule,
    ProjectModuleWorkItem,
    WorkItem,
)
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.module.ordering import ProjectModuleSortProperty
from rapidly.projects.module.queries import (
    ProjectModuleRepository,
    ProjectModuleWorkItemRepository,
)
from rapidly.projects.module.types import (
    ProjectModuleCreate,
    ProjectModuleUpdate,
)
from rapidly.projects.project.access import require_role
from rapidly.projects.project.queries import ProjectRepository

# ── Reads ──


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> ProjectModule | None:
    repo = ProjectModuleRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(ProjectModule.id == id)
    return await repo.get_one_or_none(stmt)


async def list_for_project(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    project_id: Sequence[UUID] | None = None,
    include_archived: bool = False,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[ProjectModuleSortProperty]],
) -> tuple[Sequence[ProjectModule], int]:
    repo = ProjectModuleRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject)
    if project_id is not None:
        statement = statement.where(ProjectModule.project_id.in_(project_id))
    if not include_archived:
        statement = statement.where(ProjectModule.archived_at.is_(None))
    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


async def list_work_item_ids(session: AsyncReadSession, module_id: UUID) -> list[UUID]:
    stmt = select(ProjectModuleWorkItem.work_item_id).where(
        ProjectModuleWorkItem.module_id == module_id,
        ProjectModuleWorkItem.deleted_at.is_(None),
    )
    return [row[0] for row in (await session.execute(stmt)).all()]


# ── Writes ──


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    data: ProjectModuleCreate,
) -> ProjectModule:
    project = await _ensure_member(session, auth_subject, data.project_id)
    _validate_date_range(data.start_date, data.target_date)

    repo = ProjectModuleRepository.from_session(session)
    if await repo.get_by_name(data.project_id, data.name) is not None:
        raise ResourceAlreadyExists(
            f"A module named '{data.name}' already exists in this project."
        )

    module = ProjectModule(
        project_id=project.id,
        lead_id=data.lead_id,
        name=data.name,
        description=data.description,
        status=data.status,
        start_date=data.start_date,
        target_date=data.target_date,
    )
    return await repo.create(module, flush=True)


async def update(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    module: ProjectModule,
    data: ProjectModuleUpdate,
) -> ProjectModule:
    await _ensure_member(session, auth_subject, module.project_id)
    update_dict = data.model_dump(exclude_unset=True)

    start = update_dict.get("start_date", module.start_date)
    target = update_dict.get("target_date", module.target_date)
    if "start_date" in update_dict or "target_date" in update_dict:
        _validate_date_range(start, target)

    if not update_dict:
        return module
    repo = ProjectModuleRepository.from_session(session)
    return await repo.update(module, update_dict=update_dict)


async def archive(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    module: ProjectModule,
) -> ProjectModule:
    await _ensure_member(
        session, auth_subject, module.project_id, minimum=ProjectMemberRole.admin
    )
    repo = ProjectModuleRepository.from_session(session)
    return await repo.update(module, update_dict={"archived_at": now_utc()})


async def unarchive(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    module: ProjectModule,
) -> ProjectModule:
    await _ensure_member(
        session, auth_subject, module.project_id, minimum=ProjectMemberRole.admin
    )
    repo = ProjectModuleRepository.from_session(session)
    return await repo.update(module, update_dict={"archived_at": None})


async def delete(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    module: ProjectModule,
) -> None:
    await _ensure_member(
        session, auth_subject, module.project_id, minimum=ProjectMemberRole.admin
    )
    repo = ProjectModuleRepository.from_session(session)
    await repo.soft_delete(module)


# ── Work-item membership ──


async def add_work_items(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    module: ProjectModule,
    work_item_ids: Sequence[UUID],
) -> None:
    await _ensure_member(session, auth_subject, module.project_id)
    await _verify_work_items_in_project(session, module.project_id, work_item_ids)

    repo = ProjectModuleWorkItemRepository.from_session(session)
    existing = await repo.existing_for_module(module.id)

    for wid in dict.fromkeys(work_item_ids):
        row = existing.get(wid)
        if row is not None:
            if row.deleted_at is not None:
                await repo.update(row, update_dict={"deleted_at": None})
            continue
        session.add(ProjectModuleWorkItem(module_id=module.id, work_item_id=wid))
    await session.flush()


async def remove_work_items(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    module: ProjectModule,
    work_item_ids: Sequence[UUID],
) -> None:
    await _ensure_member(session, auth_subject, module.project_id)

    repo = ProjectModuleWorkItemRepository.from_session(session)
    existing = await repo.existing_for_module(module.id)
    for wid in work_item_ids:
        row = existing.get(wid)
        if row is None or row.deleted_at is not None:
            continue
        await repo.soft_delete(row)


# ── Helpers ──


def _validate_date_range(start: datetime | None, target: datetime | None) -> None:
    if start is not None and target is not None and target < start:
        raise BadRequest("Module target_date must not precede start_date.")


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


async def _verify_work_items_in_project(
    session: AsyncSession, project_id: UUID, work_item_ids: Sequence[UUID]
) -> None:
    if not work_item_ids:
        return
    stmt = select(WorkItem.id).where(
        WorkItem.id.in_(work_item_ids),
        WorkItem.project_id == project_id,
        WorkItem.deleted_at.is_(None),
    )
    found = {row[0] for row in (await session.execute(stmt)).all()}
    missing = set(work_item_ids) - found
    if missing:
        raise BadRequest(
            "One or more work items do not belong to this module's project."
        )
