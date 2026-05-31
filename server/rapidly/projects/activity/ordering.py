"""Sort-order enum for activity list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class WorkItemActivitySortProperty(StrEnum):
    created_at = "created_at"


_DEFAULT_ORDER: list[str] = ["-created_at"]

type WorkItemActivitiesSorting = Annotated[
    list[Sorting[WorkItemActivitySortProperty]],
    Depends(SortingGetter(WorkItemActivitySortProperty, _DEFAULT_ORDER)),
]
