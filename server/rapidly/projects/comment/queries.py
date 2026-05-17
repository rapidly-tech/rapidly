"""Work-item comment persistence layer."""

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
    WorkspaceMembership,
)
from rapidly.projects.comment.ordering import WorkItemCommentSortProperty


class WorkItemCommentRepository(
    SoftDeleteMixin[WorkItemComment],
    FindByIdMixin[WorkItemComment, UUID],
    Repository[WorkItemComment],
):
    model = WorkItemComment

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[WorkItemComment]]:
        statement = (
            self.get_base_statement()
            .join(WorkItem, WorkItem.id == WorkItemComment.work_item_id)
            .join(Project, Project.id == WorkItem.project_id)
            # Soft-deleted parents (work item or project) must never
            # surface their comments to readers.
            .where(
                WorkItem.deleted_at.is_(None),
                Project.deleted_at.is_(None),
            )
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
        statement: Select[tuple[WorkItemComment]],
        sorting: Sequence[Sorting[WorkItemCommentSortProperty]],
    ) -> Select[tuple[WorkItemComment]]:
        clauses: list[UnaryExpression[Any]] = []
        for criterion, is_desc in sorting:
            fn = desc if is_desc else asc
            column = getattr(WorkItemComment, criterion.value)
            clauses.append(fn(column))
        return statement.order_by(*clauses) if clauses else statement
