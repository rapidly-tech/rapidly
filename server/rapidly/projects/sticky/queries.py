"""Sticky persistence layer."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import Select, asc, desc
from sqlalchemy.sql.elements import UnaryExpression

from rapidly.core.ordering import Sorting
from rapidly.core.queries import FindByIdMixin, Repository, SoftDeleteMixin
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.models import Sticky
from rapidly.projects.sticky.ordering import StickySortProperty


class StickyRepository(
    SoftDeleteMixin[Sticky],
    FindByIdMixin[Sticky, UUID],
    Repository[Sticky],
):
    model = Sticky

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User]
    ) -> Select[tuple[Sticky]]:
        """Hard-coded to ``owner_id = caller`` — stickies are strictly
        private."""
        return self.get_base_statement().where(
            Sticky.owner_id == auth_subject.subject.id
        )

    def apply_sorting(
        self,
        statement: Select[tuple[Sticky]],
        sorting: Sequence[Sorting[StickySortProperty]],
    ) -> Select[tuple[Sticky]]:
        clauses: list[UnaryExpression[Any]] = []
        for criterion, is_desc in sorting:
            fn = desc if is_desc else asc
            column = getattr(Sticky, criterion.value)
            clauses.append(fn(column))
        return statement.order_by(*clauses) if clauses else statement
