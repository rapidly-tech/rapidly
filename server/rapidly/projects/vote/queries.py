"""Work-item-vote persistence layer."""

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
    WorkItemVote,
    WorkspaceMembership,
)
from rapidly.projects.vote.ordering import WorkItemVoteSortProperty


class WorkItemVoteRepository(
    SoftDeleteMixin[WorkItemVote],
    FindByIdMixin[WorkItemVote, UUID],
    Repository[WorkItemVote],
):
    model = WorkItemVote

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[WorkItemVote]]:
        statement = (
            self.get_base_statement()
            .join(WorkItem, WorkItem.id == WorkItemVote.work_item_id)
            .join(Project, Project.id == WorkItem.project_id)
        )

        if is_user_principal(auth_subject):
            user = auth_subject.subject
            statement = statement.where(
                Project.workspace_id.in_(
                    select(WorkspaceMembership.workspace_id).where(
                        WorkspaceMembership.user_id == user.id,
                        WorkspaceMembership.deleted_at.is_(None),
                    )
                )
            )
        elif is_workspace_principal(auth_subject):
            statement = statement.where(Project.workspace_id == auth_subject.subject.id)

        return statement

    def apply_sorting(
        self,
        statement: Select[tuple[WorkItemVote]],
        sorting: Sequence[Sorting[WorkItemVoteSortProperty]],
    ) -> Select[tuple[WorkItemVote]]:
        clauses: list[UnaryExpression[Any]] = []
        for criterion, is_desc in sorting:
            fn = desc if is_desc else asc
            column = getattr(WorkItemVote, criterion.value)
            clauses.append(fn(column))
        return statement.order_by(*clauses) if clauses else statement

    async def get_for_work_item_and_user(
        self, work_item_id: UUID, user_id: UUID
    ) -> WorkItemVote | None:
        statement = self.get_base_statement().where(
            WorkItemVote.work_item_id == work_item_id,
            WorkItemVote.user_id == user_id,
        )
        return await self.get_one_or_none(statement)
