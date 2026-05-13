"""Sort-order enum for work-item list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class WorkItemSortProperty(StrEnum):
    sequence_number = "sequence_number"
    name = "name"
    priority = "priority"
    sort_order = "sort_order"
    start_date = "start_date"
    target_date = "target_date"
    completed_at = "completed_at"
    created_at = "created_at"
    modified_at = "modified_at"


_DEFAULT_ORDER: list[str] = ["sort_order", "-created_at"]

type WorkItemsSorting = Annotated[
    list[Sorting[WorkItemSortProperty]],
    Depends(SortingGetter(WorkItemSortProperty, _DEFAULT_ORDER)),
]
