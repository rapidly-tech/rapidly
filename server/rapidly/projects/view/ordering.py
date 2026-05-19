"""Sort-order enum for project saved-view list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class ProjectViewSortProperty(StrEnum):
    sort_order = "sort_order"
    name = "name"
    created_at = "created_at"


_DEFAULT_ORDER: list[str] = ["sort_order", "-created_at"]

type ProjectViewsSorting = Annotated[
    list[Sorting[ProjectViewSortProperty]],
    Depends(SortingGetter(ProjectViewSortProperty, _DEFAULT_ORDER)),
]
