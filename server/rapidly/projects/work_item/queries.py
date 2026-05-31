"""Work-item persistence layer with workspace scoping and project-scoped sequence helper."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import Select, asc, desc, func, select
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
from rapidly.models import Project, WorkItem, WorkspaceMembership
from rapidly.projects.work_item.ordering import WorkItemSortProperty


class WorkItemRepository(
    SoftDeleteMixin[WorkItem],
    FindByIdMixin[WorkItem, UUID],
    Repository[WorkItem],
):
    model = WorkItem

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[WorkItem]]:
        statement = self.get_base_statement().join(
            Project, Project.id == WorkItem.project_id
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
        statement: Select[tuple[WorkItem]],
        sorting: Sequence[Sorting[WorkItemSortProperty]],
    ) -> Select[tuple[WorkItem]]:
        clauses: list[UnaryExpression[Any]] = []
        for criterion, is_desc in sorting:
            fn = desc if is_desc else asc
            column = getattr(WorkItem, criterion.value)
            clauses.append(fn(column))
        return statement.order_by(*clauses) if clauses else statement

    async def next_sequence_number(self, project_id: UUID) -> int:
        """Return the next sequence number for the given project.

        Reads ``MAX(sequence_number) + 1`` via the project's own scope.
        The unique constraint ``(project_id, sequence_number)`` is the
        ultimate guard: on contention the duplicate INSERT raises and
        the caller retries.
        """
        statement = select(func.max(WorkItem.sequence_number)).where(
            WorkItem.project_id == project_id
        )
        result = await self.session.execute(statement)
        current = result.scalar_one_or_none()
        return (current or 0) + 1
