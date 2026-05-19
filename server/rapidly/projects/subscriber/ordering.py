"""Sort-order enum for work-item subscriber list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class WorkItemSubscriberSortProperty(StrEnum):
    created_at = "created_at"


_DEFAULT_ORDER: list[str] = ["-created_at"]

type WorkItemSubscribersSorting = Annotated[
    list[Sorting[WorkItemSubscriberSortProperty]],
    Depends(SortingGetter(WorkItemSubscriberSortProperty, _DEFAULT_ORDER)),
]
