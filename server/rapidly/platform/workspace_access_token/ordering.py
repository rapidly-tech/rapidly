"""Sort-order enum and dependency for workspace access token list queries."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class WorkspaceAccessTokenSortProperty(StrEnum):
    created_at = "created_at"
    comment = "comment"
    last_used_at = "last_used_at"
    workspace_id = "workspace_id"


type ListSorting = Annotated[
    list[Sorting[WorkspaceAccessTokenSortProperty]],
    Depends(SortingGetter(WorkspaceAccessTokenSortProperty, ["created_at"])),
]
