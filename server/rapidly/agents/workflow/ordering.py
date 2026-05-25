"""Sort-order enum for workflow list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class WorkflowSortProperty(StrEnum):
    name = "name"
    created_at = "created_at"
    updated_at = "updated_at"


_DEFAULT_ORDER: list[str] = ["-updated_at"]

type WorkflowsSorting = Annotated[
    list[Sorting[WorkflowSortProperty]],
    Depends(SortingGetter(WorkflowSortProperty, _DEFAULT_ORDER)),
]
