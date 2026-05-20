"""Sort-order enum for project-member invite list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class ProjectMemberInviteSortProperty(StrEnum):
    created_at = "created_at"


_DEFAULT_ORDER: list[str] = ["-created_at"]

type ProjectMemberInvitesSorting = Annotated[
    list[Sorting[ProjectMemberInviteSortProperty]],
    Depends(SortingGetter(ProjectMemberInviteSortProperty, _DEFAULT_ORDER)),
]
