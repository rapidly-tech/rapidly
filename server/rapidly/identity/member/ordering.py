"""Sort-order enum and dependency for member list queries.

Provides ``ListSorting`` as a FastAPI dependency that parses
``?sorting=-created_at`` query parameters into typed sort descriptors.
"""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class MemberSortProperty(StrEnum):
    created_at = "created_at"


_DEFAULT_ORDER: list[str] = ["-created_at"]

type ListSorting = Annotated[
    list[Sorting[MemberSortProperty]],
    Depends(SortingGetter(MemberSortProperty, _DEFAULT_ORDER)),
]
