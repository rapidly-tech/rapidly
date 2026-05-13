"""Project estimate lifecycle and point management."""

from collections.abc import Sequence
from uuid import UUID

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.errors import ResourceAlreadyExists, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models import ProjectEstimate, ProjectEstimatePoint, ProjectMemberRole
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.estimate.ordering import ProjectEstimateSortProperty
from rapidly.projects.estimate.queries import (
    ProjectEstimatePointRepository,
    ProjectEstimateRepository,
)
from rapidly.projects.estimate.types import (
    ProjectEstimateCreate,
    ProjectEstimatePointCreate,
    ProjectEstimatePointUpdate,
    ProjectEstimateUpdate,
)
from rapidly.projects.project.access import require_role
from rapidly.projects.project.queries import ProjectRepository

# ── Estimates ──


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> ProjectEstimate | None:
    repo = ProjectEstimateRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(ProjectEstimate.id == id)
    return await repo.get_one_or_none(stmt)


async def list(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    project_id: Sequence[UUID] | None = None,
    name: str | None = None,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[ProjectEstimateSortProperty]],
) -> tuple[Sequence[ProjectEstimate], int]:
    repo = ProjectEstimateRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject)
    if project_id is not None:
        statement = statement.where(ProjectEstimate.project_id.in_(project_id))
    if name is not None and name.strip():
        # Case-insensitive substring match.  ``%`` and ``_`` in the
        # input are escaped so callers cannot smuggle wildcards past
        # the documented substring semantics.
        escaped = (
            name.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        statement = statement.where(
            ProjectEstimate.name.ilike(f"%{escaped}%", escape="\\")
        )
    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    data: ProjectEstimateCreate,
) -> ProjectEstimate:
    project_repo = ProjectRepository.from_session(session)
    project = await project_repo.get_one_or_none(
        project_repo.get_readable_statement(auth_subject).where(
            project_repo.model.id == data.project_id
        )
    )
    if project is None:
        raise ResourceNotFound("Project not found.")

    await require_role(session, auth_subject, project, minimum=ProjectMemberRole.admin)

    repo = ProjectEstimateRepository.from_session(session)
    if await repo.get_by_name(data.project_id, data.name) is not None:
        raise ResourceAlreadyExists(
            f"An estimate named '{data.name}' already exists in this project."
        )

    estimate = ProjectEstimate(
        project_id=data.project_id,
        name=data.name,
        description=data.description,
        type=data.type,
        is_active=data.is_active,
    )
    return await repo.create(estimate, flush=True)


async def update(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    estimate: ProjectEstimate,
    data: ProjectEstimateUpdate,
) -> ProjectEstimate:
    await _ensure_admin(session, auth_subject, estimate.project_id)
    repo = ProjectEstimateRepository.from_session(session)
    update_dict = data.model_dump(exclude_unset=True)
    if not update_dict:
        return estimate
    return await repo.update(estimate, update_dict=update_dict)


async def delete(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    estimate: ProjectEstimate,
) -> None:
    await _ensure_admin(session, auth_subject, estimate.project_id)
    repo = ProjectEstimateRepository.from_session(session)
    await repo.soft_delete(estimate)


# ── Points ──


async def get_point(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> ProjectEstimatePoint | None:
    repo = ProjectEstimatePointRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(
        ProjectEstimatePoint.id == id
    )
    return await repo.get_one_or_none(stmt)


async def list_points(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    estimate_id: UUID,
) -> Sequence[ProjectEstimatePoint]:
    repo = ProjectEstimatePointRepository.from_session(session)
    statement = (
        repo.get_readable_statement(auth_subject)
        .where(ProjectEstimatePoint.estimate_id == estimate_id)
        .order_by(ProjectEstimatePoint.key.asc())
    )
    return await repo.get_all(statement)


async def create_point(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    data: ProjectEstimatePointCreate,
) -> ProjectEstimatePoint:
    estimate = await get(session, auth_subject, data.estimate_id)
    if estimate is None:
        raise ResourceNotFound("Estimate not found.")

    await _ensure_admin(session, auth_subject, estimate.project_id)

    repo = ProjectEstimatePointRepository.from_session(session)
    if await repo.get_by_estimate_and_key(data.estimate_id, data.key) is not None:
        raise ResourceAlreadyExists(
            f"A point with key {data.key} already exists in this estimate scale."
        )

    point = ProjectEstimatePoint(
        estimate_id=data.estimate_id,
        key=data.key,
        value=data.value,
        description=data.description,
    )
    return await repo.create(point, flush=True)


async def update_point(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    point: ProjectEstimatePoint,
    data: ProjectEstimatePointUpdate,
) -> ProjectEstimatePoint:
    estimate = await get(session, auth_subject, point.estimate_id)
    if estimate is None:
        raise ResourceNotFound("Estimate not found.")
    await _ensure_admin(session, auth_subject, estimate.project_id)

    repo = ProjectEstimatePointRepository.from_session(session)
    update_dict = data.model_dump(exclude_unset=True)
    if not update_dict:
        return point
    return await repo.update(point, update_dict=update_dict)


async def delete_point(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    point: ProjectEstimatePoint,
) -> None:
    estimate = await get(session, auth_subject, point.estimate_id)
    if estimate is None:
        raise ResourceNotFound("Estimate not found.")
    await _ensure_admin(session, auth_subject, estimate.project_id)

    repo = ProjectEstimatePointRepository.from_session(session)
    await repo.soft_delete(point)


async def _ensure_admin(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    project_id: UUID,
) -> None:
    """Estimation scales are admin-only — they shape every work item's metrics."""
    project_repo = ProjectRepository.from_session(session)
    project = await project_repo.get_one_or_none(
        project_repo.get_readable_statement(auth_subject).where(
            project_repo.model.id == project_id
        )
    )
    if project is None:
        raise ResourceNotFound("Project not found.")
    await require_role(session, auth_subject, project, minimum=ProjectMemberRole.admin)
