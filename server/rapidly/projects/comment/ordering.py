"""Sort-order enum for work-item comment list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class WorkItemCommentSortProperty(StrEnum):
    created_at = "created_at"
    modified_at = "modified_at"


_DEFAULT_ORDER: list[str] = ["created_at"]

type WorkItemCommentsSorting = Annotated[
    list[Sorting[WorkItemCommentSortProperty]],
    Depends(SortingGetter(WorkItemCommentSortProperty, _DEFAULT_ORDER)),
]
