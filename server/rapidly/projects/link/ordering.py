"""Sort-order enum for relation list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class WorkItemRelationSortProperty(StrEnum):
    created_at = "created_at"
    relation_type = "relation_type"


_DEFAULT_ORDER: list[str] = ["relation_type", "-created_at"]

type WorkItemRelationsSorting = Annotated[
    list[Sorting[WorkItemRelationSortProperty]],
    Depends(SortingGetter(WorkItemRelationSortProperty, _DEFAULT_ORDER)),
]
