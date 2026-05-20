"""Sort-order enum for sticky list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class StickySortProperty(StrEnum):
    sort_order = "sort_order"
    created_at = "created_at"


_DEFAULT_ORDER: list[str] = ["sort_order", "-created_at"]

type StickiesSorting = Annotated[
    list[Sorting[StickySortProperty]],
    Depends(SortingGetter(StickySortProperty, _DEFAULT_ORDER)),
]
