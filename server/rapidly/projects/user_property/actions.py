"""Project-user-property lifecycle: get-mine, upsert.

Strictly self-only.  Every operation acts on a row keyed by
``(project_id, caller.user_id)`` — there's no way to read or modify
another user's preferences.  No admin escape hatch; these are
purely client-driven UI state.

Upsert semantics:
- If a row exists for (project, user), partial-update it with the
  payload (fields not in the payload keep their current value).
- If no row exists, insert with the payload (missing fields default
  to empty dicts via the model's column defaults).
"""

from uuid import UUID

from sqlalchemy import select

from rapidly.errors import ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.models import Project, ProjectUserProperty, WorkspaceMembership
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.user_property.queries import ProjectUserPropertyRepository
from rapidly.projects.user_property.types import ProjectUserPropertyUpsert


async def get_mine_for_project(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User],
    project_id: UUID,
) -> ProjectUserProperty | None:
    """Return the caller's preferences for the given project, if set."""
    repo = ProjectUserPropertyRepository.from_session(session)
    return await repo.get_for_user_and_project(auth_subject.subject.id, project_id)


async def upsert(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    data: ProjectUserPropertyUpsert,
) -> ProjectUserProperty:
    """Write the caller's preferences for the given project."""
    await _ensure_project_readable(session, auth_subject, data.project_id)

    repo = ProjectUserPropertyRepository.from_session(session)
    existing = await repo.get_for_user_and_project(
        auth_subject.subject.id, data.project_id
    )

    payload = data.model_dump(exclude_unset=True, exclude={"project_id"})

    if existing is None:
        record = ProjectUserProperty(
            project_id=data.project_id,
            user_id=auth_subject.subject.id,
            filters=payload.get("filters", {}),
            display_filters=payload.get("display_filters", {}),
            display_properties=payload.get("display_properties", {}),
        )
        return await repo.create(record, flush=True)

    if not payload:
        return existing
    return await repo.update(existing, update_dict=payload)


# ── Helpers ──


async def _ensure_project_readable(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    project_id: UUID,
) -> None:
    """The caller must belong to the project's workspace.

    Why not just rely on FK: storing prefs for a project the caller
    can't see leaks the project's existence on subsequent reads via
    timing of the upsert vs. the FK violation.  Pre-checking gives a
    clean 404 instead.
    """
    stmt = (
        select(Project.id)
        .join(
            WorkspaceMembership,
            WorkspaceMembership.workspace_id == Project.workspace_id,
        )
        .where(
            Project.id == project_id,
            WorkspaceMembership.user_id == auth_subject.subject.id,
            WorkspaceMembership.deleted_at.is_(None),
        )
    )
    if (await session.execute(stmt)).scalar_one_or_none() is None:
        raise ResourceNotFound("Project not found.")
