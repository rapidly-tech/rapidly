"""Sort-order enum for work-item attachment list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class WorkItemAttachmentSortProperty(StrEnum):
    created_at = "created_at"


_DEFAULT_ORDER: list[str] = ["-created_at"]

type WorkItemAttachmentsSorting = Annotated[
    list[Sorting[WorkItemAttachmentSortProperty]],
    Depends(SortingGetter(WorkItemAttachmentSortProperty, _DEFAULT_ORDER)),
]
