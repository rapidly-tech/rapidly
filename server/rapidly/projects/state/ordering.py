"""Sort-order enum for project state list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class ProjectStateSortProperty(StrEnum):
    name = "name"
    group = "group"
    sequence = "sequence"
    created_at = "created_at"


_DEFAULT_ORDER: list[str] = ["group", "sequence"]

type ProjectStatesSorting = Annotated[
    list[Sorting[ProjectStateSortProperty]],
    Depends(SortingGetter(ProjectStateSortProperty, _DEFAULT_ORDER)),
]
