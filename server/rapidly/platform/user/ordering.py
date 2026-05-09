"""Ordering definitions for the user module.

Declares sortable columns for user list endpoints and provides
a pre-built FastAPI dependency alias.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class UserSortProperty(StrEnum):
    """Columns that user lists can be sorted by."""

    email = "email"
    created_at = "created_at"


type ListSorting = Annotated[
    list[Sorting[UserSortProperty]],
    Depends(SortingGetter(UserSortProperty, ["created_at"])),
]
