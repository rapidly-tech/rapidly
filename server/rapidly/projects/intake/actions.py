"""Intake-work-item lifecycle: list, get, create, transition (update), delete.

The transition rules form a small state machine:

  pending  → accepted | declined | snoozed | duplicate
  accepted → pending          (rare: re-open)
  declined → pending          (rare: re-open)
  snoozed  → pending | accepted | declined | duplicate
  duplicate → pending         (rare: re-triage)

Anything else returns BadRequest.  Two payload-level invariants on
the transition step:

- ``status=snoozed`` requires ``snoozed_until`` in the *future*.
  A past timestamp would silently behave as "still in queue" without
  any wake-up signal.
- ``status=duplicate`` requires ``duplicate_to_id`` pointing at a work
  item that's already readable to the caller — and not the same work
  item being triaged (an item can't dedupe to itself).

Both gate-create and gate-transition need the ``member`` project role.
"""

from collections.abc import Sequence
from uuid import UUID

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.core.utils import now_utc
from rapidly.errors import BadRequest, ResourceAlreadyExists, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models import (
    IntakeSource,
    IntakeStatus,
    IntakeWorkItem,
    Project,
    ProjectMemberRole,
    WorkItem,
)
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.intake.ordering import IntakeWorkItemSortProperty
from rapidly.projects.intake.queries import IntakeWorkItemRepository
from rapidly.projects.intake.types import IntakeWorkItemCreate, IntakeWorkItemUpdate
from rapidly.projects.project.access import require_role
from rapidly.projects.project.queries import ProjectRepository
from rapidly.projects.work_item.queries import WorkItemRepository

# Allowed status transitions. Self-loops are excluded — same-value
# updates fall through to a no-op in ``transition``.
_ALLOWED: dict[IntakeStatus, set[IntakeStatus]] = {
    IntakeStatus.pending: {
        IntakeStatus.accepted,
        IntakeStatus.declined,
        IntakeStatus.snoozed,
        IntakeStatus.duplicate,
    },
    IntakeStatus.accepted: {IntakeStatus.pending},
    IntakeStatus.declined: {IntakeStatus.pending},
    IntakeStatus.snoozed: {
        IntakeStatus.pending,
        IntakeStatus.accepted,
        IntakeStatus.declined,
        IntakeStatus.duplicate,
    },
    IntakeStatus.duplicate: {IntakeStatus.pending},
}


# ── Reads ──


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> IntakeWorkItem | None:
    repo = IntakeWorkItemRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(IntakeWorkItem.id == id)
    return await repo.get_one_or_none(stmt)


async def list_for_project(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    project_id: UUID,
    status: IntakeStatus | None = None,
    source: IntakeSource | None = None,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[IntakeWorkItemSortProperty]],
) -> tuple[Sequence[IntakeWorkItem], int]:
    await _ensure_member(session, auth_subject, project_id)

    repo = IntakeWorkItemRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject).where(
        WorkItem.project_id == project_id
    )
    if status is not None:
        statement = statement.where(IntakeWorkItem.status == status)
    if source is not None:
        statement = statement.where(IntakeWorkItem.source == source)
    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


# ── Writes ──


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    data: IntakeWorkItemCreate,
) -> IntakeWorkItem:
    work_item = await _readable_work_item(session, auth_subject, data.work_item_id)
    await _ensure_member(session, auth_subject, work_item.project_id)

    repo = IntakeWorkItemRepository.from_session(session)
    if await repo.get_by_work_item(data.work_item_id) is not None:
        raise ResourceAlreadyExists("This work item is already in the intake queue.")

    record = IntakeWorkItem(
        work_item_id=data.work_item_id,
        status=IntakeStatus.pending,
        source=data.source,
        source_email=data.source_email,
    )
    return await repo.create(record, flush=True)


async def transition(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    intake: IntakeWorkItem,
    data: IntakeWorkItemUpdate,
) -> IntakeWorkItem:
    """Apply a status change to an intake row."""
    work_item = await _readable_work_item(session, auth_subject, intake.work_item_id)
    await _ensure_member(session, auth_subject, work_item.project_id)

    if data.status == intake.status:
        return intake

    allowed = _ALLOWED.get(intake.status, set())
    if data.status not in allowed:
        raise BadRequest(
            f"Cannot transition from {intake.status.value} to {data.status.value}."
        )

    update_dict: dict[str, object] = {
        "status": data.status,
        "snoozed_until": None,
        "duplicate_to_id": None,
        "triaged_at": now_utc(),
        "triaged_by_id": (
            auth_subject.subject.id if isinstance(auth_subject.subject, User) else None
        ),
    }

    if data.status == IntakeStatus.snoozed:
        if data.snoozed_until is None or data.snoozed_until <= now_utc():
            raise BadRequest("snoozed_until must be a future timestamp.")
        update_dict["snoozed_until"] = data.snoozed_until

    if data.status == IntakeStatus.duplicate:
        if data.duplicate_to_id is None:
            raise BadRequest("duplicate_to_id is required when status=duplicate.")
        if data.duplicate_to_id == intake.work_item_id:
            raise BadRequest("A work item cannot be a duplicate of itself.")
        # Caller must be able to read the target — and it must be in
        # the same project as the intake item.
        target = await _readable_work_item(session, auth_subject, data.duplicate_to_id)
        if target.project_id != work_item.project_id:
            raise BadRequest("Duplicate target must be in the same project.")
        update_dict["duplicate_to_id"] = data.duplicate_to_id

    repo = IntakeWorkItemRepository.from_session(session)
    return await repo.update(intake, update_dict=update_dict)


async def delete(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    intake: IntakeWorkItem,
) -> None:
    """Remove an intake row.

    The underlying ``WorkItem`` is intentionally *not* deleted — a
    declined item often stays around as evidence; the caller can
    delete the work item separately if they want it gone.
    """
    work_item = await _readable_work_item(session, auth_subject, intake.work_item_id)
    await _ensure_member(session, auth_subject, work_item.project_id)
    repo = IntakeWorkItemRepository.from_session(session)
    await repo.soft_delete(intake)


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
    session: AsyncSession | AsyncReadSession,
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
