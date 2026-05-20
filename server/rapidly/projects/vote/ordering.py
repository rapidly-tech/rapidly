"""Sort-order enum for work-item vote list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class WorkItemVoteSortProperty(StrEnum):
    created_at = "created_at"


_DEFAULT_ORDER: list[str] = ["-created_at"]

type WorkItemVotesSorting = Annotated[
    list[Sorting[WorkItemVoteSortProperty]],
    Depends(SortingGetter(WorkItemVoteSortProperty, _DEFAULT_ORDER)),
]
