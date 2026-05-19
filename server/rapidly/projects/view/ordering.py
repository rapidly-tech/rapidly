"""Sort-order enum for project-view list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class ProjectViewSortProperty(StrEnum):
    name = "name"
    created_at = "created_at"
    modified_at = "modified_at"


_DEFAULT_ORDER: list[str] = ["-modified_at"]

type ProjectViewsSorting = Annotated[
    list[Sorting[ProjectViewSortProperty]],
    Depends(SortingGetter(ProjectViewSortProperty, _DEFAULT_ORDER)),
]
