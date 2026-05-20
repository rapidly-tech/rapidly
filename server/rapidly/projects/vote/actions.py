"""Work-item-vote lifecycle: list, cast (upsert), retract.

``cast`` is an upsert keyed by ``(work_item_id, caller)`` — flipping
your vote (e.g. from upvote to downvote) updates the existing row
rather than inserting a second.

Retract is the DELETE — soft-deletes the row so re-casting later
doesn't trip the uniqueness guard.  (The repo uses ``SoftDeleteMixin``;
casting after a retract re-uses the same logical row but the soft-
deleted predecessor stays in the audit log.)
"""

from collections.abc import Sequence
from uuid import UUID

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.errors import ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models import WorkItem, WorkItemVote
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.vote.ordering import WorkItemVoteSortProperty
from rapidly.projects.vote.queries import WorkItemVoteRepository
from rapidly.projects.vote.types import WorkItemVoteCast
from rapidly.projects.work_item.queries import WorkItemRepository

# ── Reads ──


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> WorkItemVote | None:
    repo = WorkItemVoteRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(WorkItemVote.id == id)
    return await repo.get_one_or_none(stmt)


async def list_for_work_item(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    work_item_id: UUID,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[WorkItemVoteSortProperty]],
) -> tuple[Sequence[WorkItemVote], int]:
    await _readable_work_item(session, auth_subject, work_item_id)
    repo = WorkItemVoteRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject).where(
        WorkItemVote.work_item_id == work_item_id
    )
    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


# ── Writes ──


async def cast(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    data: WorkItemVoteCast,
) -> WorkItemVote:
    """Cast or recast the caller's vote on a work item."""
    await _readable_work_item(session, auth_subject, data.work_item_id)

    repo = WorkItemVoteRepository.from_session(session)
    existing = await repo.get_for_work_item_and_user(
        data.work_item_id, auth_subject.subject.id
    )
    if existing is not None:
        if existing.vote == data.vote:
            return existing
        return await repo.update(existing, update_dict={"vote": data.vote})

    record = WorkItemVote(
        work_item_id=data.work_item_id,
        user_id=auth_subject.subject.id,
        vote=data.vote,
    )
    return await repo.create(record, flush=True)


async def retract(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    vote: WorkItemVote,
) -> None:
    if vote.user_id != auth_subject.subject.id:
        # 404 not 403 — non-owners shouldn't be able to oracle a row.
        raise ResourceNotFound()
    repo = WorkItemVoteRepository.from_session(session)
    await repo.soft_delete(vote)


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
