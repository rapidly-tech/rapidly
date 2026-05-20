"""Cycle/module user-property lifecycle.

Same shape as #714 (ProjectUserProperty): self-only get + upsert,
with an existence-leak guard that pre-checks readability of the
parent resource through the workspace boundary.

The two flows share helpers in ``_readable_cycle`` / ``_readable_module``
— each pre-resolves the parent row via the project→workspace join
so storing prefs for a resource the caller can't see returns a clean
404 instead of leaking via FK violation timing.
"""

from uuid import UUID

from sqlalchemy import select

from rapidly.errors import ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.models import (
    Project,
    ProjectCycle,
    ProjectCycleUserProperty,
    ProjectModule,
    ProjectModuleUserProperty,
    WorkspaceMembership,
)
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.resource_user_property.queries import (
    ProjectCycleUserPropertyRepository,
    ProjectModuleUserPropertyRepository,
)
from rapidly.projects.resource_user_property.types import (
    ProjectCycleUserPropertyUpsert,
    ProjectModuleUserPropertyUpsert,
)

# ── Cycles ───────────────────────────────────────────────────────────


async def get_cycle_props(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User],
    cycle_id: UUID,
) -> ProjectCycleUserProperty | None:
    repo = ProjectCycleUserPropertyRepository.from_session(session)
    return await repo.get_for_user_and_cycle(auth_subject.subject.id, cycle_id)


async def upsert_cycle_props(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    data: ProjectCycleUserPropertyUpsert,
) -> ProjectCycleUserProperty:
    await _ensure_cycle_readable(session, auth_subject, data.cycle_id)

    repo = ProjectCycleUserPropertyRepository.from_session(session)
    existing = await repo.get_for_user_and_cycle(auth_subject.subject.id, data.cycle_id)

    payload = data.model_dump(exclude_unset=True, exclude={"cycle_id"})

    if existing is None:
        record = ProjectCycleUserProperty(
            cycle_id=data.cycle_id,
            user_id=auth_subject.subject.id,
            filters=payload.get("filters", {}),
            display_filters=payload.get("display_filters", {}),
            display_properties=payload.get("display_properties", {}),
        )
        return await repo.create(record, flush=True)

    if not payload:
        return existing
    return await repo.update(existing, update_dict=payload)


# ── Modules ──────────────────────────────────────────────────────────


async def get_module_props(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User],
    module_id: UUID,
) -> ProjectModuleUserProperty | None:
    repo = ProjectModuleUserPropertyRepository.from_session(session)
    return await repo.get_for_user_and_module(auth_subject.subject.id, module_id)


async def upsert_module_props(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    data: ProjectModuleUserPropertyUpsert,
) -> ProjectModuleUserProperty:
    await _ensure_module_readable(session, auth_subject, data.module_id)

    repo = ProjectModuleUserPropertyRepository.from_session(session)
    existing = await repo.get_for_user_and_module(
        auth_subject.subject.id, data.module_id
    )

    payload = data.model_dump(exclude_unset=True, exclude={"module_id"})

    if existing is None:
        record = ProjectModuleUserProperty(
            module_id=data.module_id,
            user_id=auth_subject.subject.id,
            filters=payload.get("filters", {}),
            display_filters=payload.get("display_filters", {}),
            display_properties=payload.get("display_properties", {}),
        )
        return await repo.create(record, flush=True)

    if not payload:
        return existing
    return await repo.update(existing, update_dict=payload)


# ── Helpers ──────────────────────────────────────────────────────────


async def _ensure_cycle_readable(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    cycle_id: UUID,
) -> None:
    stmt = (
        select(ProjectCycle.id)
        .join(Project, Project.id == ProjectCycle.project_id)
        .join(
            WorkspaceMembership,
            WorkspaceMembership.workspace_id == Project.workspace_id,
        )
        .where(
            ProjectCycle.id == cycle_id,
            WorkspaceMembership.user_id == auth_subject.subject.id,
            WorkspaceMembership.deleted_at.is_(None),
        )
    )
    if (await session.execute(stmt)).scalar_one_or_none() is None:
        raise ResourceNotFound("Cycle not found.")


async def _ensure_module_readable(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    module_id: UUID,
) -> None:
    stmt = (
        select(ProjectModule.id)
        .join(Project, Project.id == ProjectModule.project_id)
        .join(
            WorkspaceMembership,
            WorkspaceMembership.workspace_id == Project.workspace_id,
        )
        .where(
            ProjectModule.id == module_id,
            WorkspaceMembership.user_id == auth_subject.subject.id,
            WorkspaceMembership.deleted_at.is_(None),
        )
    )
    if (await session.execute(stmt)).scalar_one_or_none() is None:
        raise ResourceNotFound("Module not found.")
