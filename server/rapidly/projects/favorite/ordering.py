"""Sort-order enum for user favorite list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class UserFavoriteSortProperty(StrEnum):
    created_at = "created_at"


_DEFAULT_ORDER: list[str] = ["-created_at"]

type UserFavoritesSorting = Annotated[
    list[Sorting[UserFavoriteSortProperty]],
    Depends(SortingGetter(UserFavoriteSortProperty, _DEFAULT_ORDER)),
]
