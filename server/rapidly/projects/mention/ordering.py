"""Sort-order enum for work-item-mention list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class WorkItemMentionSortProperty(StrEnum):
    created_at = "created_at"


_DEFAULT_ORDER: list[str] = ["-created_at"]

type WorkItemMentionsSorting = Annotated[
    list[Sorting[WorkItemMentionSortProperty]],
    Depends(SortingGetter(WorkItemMentionSortProperty, _DEFAULT_ORDER)),
]
