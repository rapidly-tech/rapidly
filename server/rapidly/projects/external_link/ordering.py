"""Sort-order enum for work-item external link list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class WorkItemLinkSortProperty(StrEnum):
    created_at = "created_at"


_DEFAULT_ORDER: list[str] = ["-created_at"]

type WorkItemLinksSorting = Annotated[
    list[Sorting[WorkItemLinkSortProperty]],
    Depends(SortingGetter(WorkItemLinkSortProperty, _DEFAULT_ORDER)),
]
