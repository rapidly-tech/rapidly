"""Sort-order enum for intake-work-item list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class IntakeWorkItemSortProperty(StrEnum):
    created_at = "created_at"
    triaged_at = "triaged_at"


_DEFAULT_ORDER: list[str] = ["-created_at"]

type IntakeWorkItemsSorting = Annotated[
    list[Sorting[IntakeWorkItemSortProperty]],
    Depends(SortingGetter(IntakeWorkItemSortProperty, _DEFAULT_ORDER)),
]
