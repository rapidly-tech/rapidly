"""Sort-order enum and dependency for workspace list queries."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class WorkspaceSortProperty(StrEnum):
    created_at = "created_at"
    slug = "slug"
    workspace_name = "name"  # `name` is a reserved word, so we use `workspace_name`
    next_review_threshold = "next_review_threshold"
    days_in_status = "days_in_status"


type ListSorting = Annotated[
    list[Sorting[WorkspaceSortProperty]],
    Depends(SortingGetter(WorkspaceSortProperty, ["created_at"])),
]
