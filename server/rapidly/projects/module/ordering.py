"""Sort-order enum for module list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class ProjectModuleSortProperty(StrEnum):
    name = "name"
    status = "status"
    start_date = "start_date"
    target_date = "target_date"
    created_at = "created_at"


_DEFAULT_ORDER: list[str] = ["-created_at"]

type ProjectModulesSorting = Annotated[
    list[Sorting[ProjectModuleSortProperty]],
    Depends(SortingGetter(ProjectModuleSortProperty, _DEFAULT_ORDER)),
]
