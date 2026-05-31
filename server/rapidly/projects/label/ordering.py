"""Sort-order enum for project label list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class ProjectLabelSortProperty(StrEnum):
    name = "name"
    created_at = "created_at"


_DEFAULT_ORDER: list[str] = ["name"]

type ProjectLabelsSorting = Annotated[
    list[Sorting[ProjectLabelSortProperty]],
    Depends(SortingGetter(ProjectLabelSortProperty, _DEFAULT_ORDER)),
]
