"""Sort-order enum for project list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class ProjectSortProperty(StrEnum):
    name = "name"
    identifier = "identifier"
    slug = "slug"
    created_at = "created_at"
    modified_at = "modified_at"
    archived_at = "archived_at"


_DEFAULT_ORDER: list[str] = ["-created_at"]

type ProjectsSorting = Annotated[
    list[Sorting[ProjectSortProperty]],
    Depends(SortingGetter(ProjectSortProperty, _DEFAULT_ORDER)),
]
