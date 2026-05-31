"""Relation lifecycle: list, get, create, delete.

Relations are immutable once created — to change the verb, delete the
edge and create a new one.  This keeps the audit trail honest.

Invariants:

- ``work_item_id`` and ``related_id`` MUST belong to the same project.
- ``work_item_id != related_id`` (also enforced by a CHECK constraint).
- ``(work_item_id, related_id, relation_type)`` is unique (also enforced
  by a UNIQUE constraint).
"""

from collections.abc import Sequence
from uuid import UUID

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.errors import BadRequest, ResourceAlreadyExists, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models import ProjectMemberRole, WorkItem, WorkItemRelation
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.link.ordering import WorkItemRelationSortProperty
from rapidly.projects.link.queries import WorkItemRelationRepository
from rapidly.projects.link.types import WorkItemRelationCreate
from rapidly.projects.project.access import require_role
from rapidly.projects.project.queries import ProjectRepository
from rapidly.projects.work_item.queries import WorkItemRepository

# ── Reads ──


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> WorkItemRelation | None:
    repo = WorkItemRelationRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(WorkItemRelation.id == id)
    return await repo.get_one_or_none(stmt)


async def list_for_work_item(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    work_item_id: UUID,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[WorkItemRelationSortProperty]],
) -> tuple[Sequence[WorkItemRelation], int]:
    # Confirm the caller can read the work item; the repo's readable
    # statement filters by workspace membership but is one indirection
    # removed from the work-item filter.
    await _readable_work_item(session, auth_subject, work_item_id)

    repo = WorkItemRelationRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject).where(
        (WorkItemRelation.work_item_id == work_item_id)
        | (WorkItemRelation.related_id == work_item_id)
    )
    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


# ── Writes ──


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    data: WorkItemRelationCreate,
) -> WorkItemRelation:
    if data.work_item_id == data.related_id:
        raise BadRequest("A work item cannot relate to itself.")

    source = await _readable_work_item(session, auth_subject, data.work_item_id)
    target = await _readable_work_item(session, auth_subject, data.related_id)

    if source.project_id != target.project_id:
        raise BadRequest("Relations across projects are not supported.")

    project_repo = ProjectRepository.from_session(session)
    project = await project_repo.get_one_or_none(
        project_repo.get_readable_statement(auth_subject).where(
            project_repo.model.id == source.project_id
        )
    )
    if project is None:
        raise ResourceNotFound("Project not found.")
    await require_role(session, auth_subject, project, minimum=ProjectMemberRole.member)

    repo = WorkItemRelationRepository.from_session(session)
    existing = await repo.get_one_or_none(
        repo.get_base_statement().where(
            WorkItemRelation.work_item_id == data.work_item_id,
            WorkItemRelation.related_id == data.related_id,
            WorkItemRelation.relation_type == data.relation_type,
        )
    )
    if existing is not None:
        raise ResourceAlreadyExists(
            f"A '{data.relation_type.value}' relation already exists between these work items."
        )

    relation = WorkItemRelation(
        work_item_id=data.work_item_id,
        related_id=data.related_id,
        relation_type=data.relation_type,
    )
    return await repo.create(relation, flush=True)


async def delete(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    relation: WorkItemRelation,
) -> None:
    source = await _readable_work_item(session, auth_subject, relation.work_item_id)
    project_repo = ProjectRepository.from_session(session)
    project = await project_repo.get_one_or_none(
        project_repo.get_readable_statement(auth_subject).where(
            project_repo.model.id == source.project_id
        )
    )
    if project is None:
        raise ResourceNotFound("Project not found.")
    await require_role(session, auth_subject, project, minimum=ProjectMemberRole.member)

    repo = WorkItemRelationRepository.from_session(session)
    await repo.soft_delete(relation)


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
