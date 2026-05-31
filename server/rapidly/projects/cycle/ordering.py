"""Sort-order enum for cycle list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class ProjectCycleSortProperty(StrEnum):
    name = "name"
    start_date = "start_date"
    end_date = "end_date"
    created_at = "created_at"


_DEFAULT_ORDER: list[str] = ["-start_date", "-created_at"]

type ProjectCyclesSorting = Annotated[
    list[Sorting[ProjectCycleSortProperty]],
    Depends(SortingGetter(ProjectCycleSortProperty, _DEFAULT_ORDER)),
]
