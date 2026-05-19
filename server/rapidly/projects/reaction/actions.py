"""Emoji-reaction lifecycle for work items and comments.

The two flows are symmetric: read access requires being able to read
the parent (work item or comment), and adding/removing a reaction is a
self-only action — a user can only add or remove their own reactions.

A removed reaction is *hard-removed* in spirit (soft-delete from
``BaseEntity`` is used internally) so re-adding the same emoji after
removal works without a uniqueness clash.
"""

from collections.abc import Sequence
from uuid import UUID

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.errors import ResourceAlreadyExists, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models import (
    WorkItem,
    WorkItemComment,
    WorkItemCommentReaction,
    WorkItemReaction,
)
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.comment.queries import WorkItemCommentRepository
from rapidly.projects.reaction.ordering import ReactionSortProperty
from rapidly.projects.reaction.queries import (
    WorkItemCommentReactionRepository,
    WorkItemReactionRepository,
)
from rapidly.projects.reaction.types import (
    WorkItemCommentReactionCreate,
    WorkItemReactionCreate,
)
from rapidly.projects.work_item.queries import WorkItemRepository

# ── Work-item reactions ──────────────────────────────────────────────


async def get_work_item_reaction(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> WorkItemReaction | None:
    repo = WorkItemReactionRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(WorkItemReaction.id == id)
    return await repo.get_one_or_none(stmt)


async def list_work_item_reactions(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    work_item_id: UUID,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[ReactionSortProperty]],
) -> tuple[Sequence[WorkItemReaction], int]:
    await _readable_work_item(session, auth_subject, work_item_id)
    repo = WorkItemReactionRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject).where(
        WorkItemReaction.work_item_id == work_item_id
    )
    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


async def react_to_work_item(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    data: WorkItemReactionCreate,
) -> WorkItemReaction:
    await _readable_work_item(session, auth_subject, data.work_item_id)
    repo = WorkItemReactionRepository.from_session(session)

    existing = await repo.get_for_triplet(
        data.work_item_id, auth_subject.subject.id, data.reaction
    )
    if existing is not None:
        raise ResourceAlreadyExists(
            "You have already reacted with this emoji on this work item."
        )

    record = WorkItemReaction(
        work_item_id=data.work_item_id,
        user_id=auth_subject.subject.id,
        reaction=data.reaction,
    )
    return await repo.create(record, flush=True)


async def unreact_work_item(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    reaction: WorkItemReaction,
) -> None:
    if reaction.user_id != auth_subject.subject.id:
        # 404 not 403 — non-owners shouldn't be able to oracle a row's
        # existence by probing the delete endpoint.
        raise ResourceNotFound()
    repo = WorkItemReactionRepository.from_session(session)
    await repo.soft_delete(reaction)


# ── Comment reactions ────────────────────────────────────────────────


async def get_comment_reaction(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> WorkItemCommentReaction | None:
    repo = WorkItemCommentReactionRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(
        WorkItemCommentReaction.id == id
    )
    return await repo.get_one_or_none(stmt)


async def list_comment_reactions(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    comment_id: UUID,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[ReactionSortProperty]],
) -> tuple[Sequence[WorkItemCommentReaction], int]:
    await _readable_comment(session, auth_subject, comment_id)
    repo = WorkItemCommentReactionRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject).where(
        WorkItemCommentReaction.comment_id == comment_id
    )
    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


async def react_to_comment(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    data: WorkItemCommentReactionCreate,
) -> WorkItemCommentReaction:
    await _readable_comment(session, auth_subject, data.comment_id)
    repo = WorkItemCommentReactionRepository.from_session(session)

    existing = await repo.get_for_triplet(
        data.comment_id, auth_subject.subject.id, data.reaction
    )
    if existing is not None:
        raise ResourceAlreadyExists(
            "You have already reacted with this emoji on this comment."
        )

    record = WorkItemCommentReaction(
        comment_id=data.comment_id,
        user_id=auth_subject.subject.id,
        reaction=data.reaction,
    )
    return await repo.create(record, flush=True)


async def unreact_comment(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    reaction: WorkItemCommentReaction,
) -> None:
    if reaction.user_id != auth_subject.subject.id:
        raise ResourceNotFound()
    repo = WorkItemCommentReactionRepository.from_session(session)
    await repo.soft_delete(reaction)


# ── Helpers ──────────────────────────────────────────────────────────


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


async def _readable_comment(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    comment_id: UUID,
) -> WorkItemComment:
    repo = WorkItemCommentRepository.from_session(session)
    comment = await repo.get_one_or_none(
        repo.get_readable_statement(auth_subject).where(
            WorkItemComment.id == comment_id
        )
    )
    if comment is None:
        raise ResourceNotFound("Comment not found.")
    return comment
