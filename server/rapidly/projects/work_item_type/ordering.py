"""Sort-order enum for work-item-type list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class WorkItemTypeSortProperty(StrEnum):
    sort_order = "sort_order"
    name = "name"
    created_at = "created_at"


_DEFAULT_ORDER: list[str] = ["sort_order", "name"]

type WorkItemTypesSorting = Annotated[
    list[Sorting[WorkItemTypeSortProperty]],
    Depends(SortingGetter(WorkItemTypeSortProperty, _DEFAULT_ORDER)),
]
