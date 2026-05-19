"""Reaction persistence layer for work items and comments."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import Select, asc, desc, select
from sqlalchemy.sql.elements import UnaryExpression

from rapidly.core.ordering import Sorting
from rapidly.core.queries import FindByIdMixin, Repository, SoftDeleteMixin
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    Workspace,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import (
    Project,
    WorkItem,
    WorkItemComment,
    WorkItemCommentReaction,
    WorkItemReaction,
    WorkspaceMembership,
)
from rapidly.projects.reaction.ordering import ReactionSortProperty


def _workspace_filter(
    statement: Select[Any], auth_subject: AuthPrincipal[User | Workspace]
) -> Select[Any]:
    """Apply the standard workspace-bounded read filter."""
    if is_user_principal(auth_subject):
        user = auth_subject.subject
        return statement.where(
            Project.workspace_id.in_(
                select(WorkspaceMembership.workspace_id).where(
                    WorkspaceMembership.user_id == user.id,
                    WorkspaceMembership.deleted_at.is_(None),
                )
            )
        )
    if is_workspace_principal(auth_subject):
        return statement.where(Project.workspace_id == auth_subject.subject.id)
    return statement


def _sort(
    statement: Select[Any],
    model: Any,
    sorting: Sequence[Sorting[ReactionSortProperty]],
) -> Select[Any]:
    clauses: list[UnaryExpression[Any]] = []
    for criterion, is_desc in sorting:
        fn = desc if is_desc else asc
        column = getattr(model, criterion.value)
        clauses.append(fn(column))
    return statement.order_by(*clauses) if clauses else statement


class WorkItemReactionRepository(
    SoftDeleteMixin[WorkItemReaction],
    FindByIdMixin[WorkItemReaction, UUID],
    Repository[WorkItemReaction],
):
    model = WorkItemReaction

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[WorkItemReaction]]:
        statement = (
            self.get_base_statement()
            .join(WorkItem, WorkItem.id == WorkItemReaction.work_item_id)
            .join(Project, Project.id == WorkItem.project_id)
        )
        return _workspace_filter(statement, auth_subject)

    def apply_sorting(
        self,
        statement: Select[tuple[WorkItemReaction]],
        sorting: Sequence[Sorting[ReactionSortProperty]],
    ) -> Select[tuple[WorkItemReaction]]:
        return _sort(statement, WorkItemReaction, sorting)

    async def get_for_triplet(
        self, work_item_id: UUID, user_id: UUID, reaction: str
    ) -> WorkItemReaction | None:
        statement = self.get_base_statement().where(
            WorkItemReaction.work_item_id == work_item_id,
            WorkItemReaction.user_id == user_id,
            WorkItemReaction.reaction == reaction,
        )
        return await self.get_one_or_none(statement)


class WorkItemCommentReactionRepository(
    SoftDeleteMixin[WorkItemCommentReaction],
    FindByIdMixin[WorkItemCommentReaction, UUID],
    Repository[WorkItemCommentReaction],
):
    model = WorkItemCommentReaction

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[WorkItemCommentReaction]]:
        statement = (
            self.get_base_statement()
            .join(
                WorkItemComment,
                WorkItemComment.id == WorkItemCommentReaction.comment_id,
            )
            .join(WorkItem, WorkItem.id == WorkItemComment.work_item_id)
            .join(Project, Project.id == WorkItem.project_id)
        )
        return _workspace_filter(statement, auth_subject)

    def apply_sorting(
        self,
        statement: Select[tuple[WorkItemCommentReaction]],
        sorting: Sequence[Sorting[ReactionSortProperty]],
    ) -> Select[tuple[WorkItemCommentReaction]]:
        return _sort(statement, WorkItemCommentReaction, sorting)

    async def get_for_triplet(
        self, comment_id: UUID, user_id: UUID, reaction: str
    ) -> WorkItemCommentReaction | None:
        statement = self.get_base_statement().where(
            WorkItemCommentReaction.comment_id == comment_id,
            WorkItemCommentReaction.user_id == user_id,
            WorkItemCommentReaction.reaction == reaction,
        )
        return await self.get_one_or_none(statement)
