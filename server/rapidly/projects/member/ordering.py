"""Sort-order enum for project-member list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class ProjectMemberSortProperty(StrEnum):
    role = "role"
    created_at = "created_at"


_DEFAULT_ORDER: list[str] = ["-created_at"]

type ProjectMembersSorting = Annotated[
    list[Sorting[ProjectMemberSortProperty]],
    Depends(SortingGetter(ProjectMemberSortProperty, _DEFAULT_ORDER)),
]
