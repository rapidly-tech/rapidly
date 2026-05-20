"""Analytic-view persistence layer."""

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
from rapidly.models import AnalyticView, WorkspaceMembership
from rapidly.projects.analytic_view.ordering import AnalyticViewSortProperty


class AnalyticViewRepository(
    SoftDeleteMixin[AnalyticView],
    FindByIdMixin[AnalyticView, UUID],
    Repository[AnalyticView],
):
    model = AnalyticView

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[AnalyticView]]:
        statement = self.get_base_statement()

        if is_user_principal(auth_subject):
            user = auth_subject.subject
            statement = statement.where(
                AnalyticView.workspace_id.in_(
                    select(WorkspaceMembership.workspace_id).where(
                        WorkspaceMembership.user_id == user.id,
                        WorkspaceMembership.deleted_at.is_(None),
                    )
                )
            )
        elif is_workspace_principal(auth_subject):
            statement = statement.where(
                AnalyticView.workspace_id == auth_subject.subject.id
            )

        return statement

    def apply_sorting(
        self,
        statement: Select[tuple[AnalyticView]],
        sorting: Sequence[Sorting[AnalyticViewSortProperty]],
    ) -> Select[tuple[AnalyticView]]:
        clauses: list[UnaryExpression[Any]] = []
        for criterion, is_desc in sorting:
            fn = desc if is_desc else asc
            column = getattr(AnalyticView, criterion.value)
            clauses.append(fn(column))
        return statement.order_by(*clauses) if clauses else statement
