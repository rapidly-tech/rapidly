"""Sort-order enum for reaction list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class ReactionSortProperty(StrEnum):
    created_at = "created_at"


_DEFAULT_ORDER: list[str] = ["created_at"]

type ReactionSorting = Annotated[
    list[Sorting[ReactionSortProperty]],
    Depends(SortingGetter(ReactionSortProperty, _DEFAULT_ORDER)),
]
