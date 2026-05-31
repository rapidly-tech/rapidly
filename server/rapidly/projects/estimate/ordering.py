"""Sort-order enum for project estimate list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class ProjectEstimateSortProperty(StrEnum):
    name = "name"
    created_at = "created_at"


_DEFAULT_ORDER: list[str] = ["-created_at"]

type ProjectEstimatesSorting = Annotated[
    list[Sorting[ProjectEstimateSortProperty]],
    Depends(SortingGetter(ProjectEstimateSortProperty, _DEFAULT_ORDER)),
]
