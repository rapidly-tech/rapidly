"""Project saved-view persistence layer."""

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
    ProjectView,
    ProjectViewAccess,
    WorkspaceMembership,
)
from rapidly.projects.view.ordering import ProjectViewSortProperty


class ProjectViewRepository(
    SoftDeleteMixin[ProjectView],
    FindByIdMixin[ProjectView, UUID],
    Repository[ProjectView],
):
    model = ProjectView

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[ProjectView]]:
        statement = self.get_base_statement().join(
            Project, Project.id == ProjectView.project_id
        )

        if is_user_principal(auth_subject):
            user = auth_subject.subject
            statement = statement.where(
                Project.workspace_id.in_(
                    select(WorkspaceMembership.workspace_id).where(
                        WorkspaceMembership.user_id == user.id,
                        WorkspaceMembership.deleted_at.is_(None),
                    )
                ),
                # Private views are visible only to their owner.  Workspace
                # tokens see every view in their own workspace via the
                # workspace-principal branch below.
                (ProjectView.access == ProjectViewAccess.public)
                | (ProjectView.owner_id == user.id),
            )
        elif is_workspace_principal(auth_subject):
            statement = statement.where(Project.workspace_id == auth_subject.subject.id)

        return statement

    def apply_sorting(
        self,
        statement: Select[tuple[ProjectView]],
        sorting: Sequence[Sorting[ProjectViewSortProperty]],
    ) -> Select[tuple[ProjectView]]:
        clauses: list[UnaryExpression[Any]] = []
        for criterion, is_desc in sorting:
            fn = desc if is_desc else asc
            column = getattr(ProjectView, criterion.value)
            clauses.append(fn(column))
        return statement.order_by(*clauses) if clauses else statement
