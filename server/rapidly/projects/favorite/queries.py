"""User favorite persistence layer.

Favorites are strictly user-scoped — ``get_readable_statement`` filters
to ``UserFavorite.user_id == auth_principal.subject.id``.  No project or
workspace join is needed: the action layer enforces that the *target*
entity (project / cycle / module / page / work item) is reachable
through its own repository before persisting.
"""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import Select, asc, desc
from sqlalchemy.sql.elements import UnaryExpression

from rapidly.core.ordering import Sorting
from rapidly.core.queries import FindByIdMixin, Repository, SoftDeleteMixin
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.models import UserFavorite
from rapidly.projects.favorite.ordering import UserFavoriteSortProperty


class UserFavoriteRepository(
    SoftDeleteMixin[UserFavorite],
    FindByIdMixin[UserFavorite, UUID],
    Repository[UserFavorite],
):
    model = UserFavorite

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User]
    ) -> Select[tuple[UserFavorite]]:
        return self.get_base_statement().where(
            UserFavorite.user_id == auth_subject.subject.id
        )

    def apply_sorting(
        self,
        statement: Select[tuple[UserFavorite]],
        sorting: Sequence[Sorting[UserFavoriteSortProperty]],
    ) -> Select[tuple[UserFavorite]]:
        clauses: list[UnaryExpression[Any]] = []
        for criterion, is_desc in sorting:
            fn = desc if is_desc else asc
            column = getattr(UserFavorite, criterion.value)
            clauses.append(fn(column))
        return statement.order_by(*clauses) if clauses else statement
