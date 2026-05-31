"""Sort-order enum for page list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class ProjectPageSortProperty(StrEnum):
    name = "name"
    created_at = "created_at"
    modified_at = "modified_at"


_DEFAULT_ORDER: list[str] = ["-modified_at", "-created_at"]

type ProjectPagesSorting = Annotated[
    list[Sorting[ProjectPageSortProperty]],
    Depends(SortingGetter(ProjectPageSortProperty, _DEFAULT_ORDER)),
]
