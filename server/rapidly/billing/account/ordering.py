"""Ordering definitions for the billing account module.

Declares sortable columns for account list endpoints and provides
a pre-built FastAPI dependency alias.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class AccountSortProperty(StrEnum):
    """Columns that account lists can be sorted by."""

    created_at = "created_at"


type ListSorting = Annotated[
    list[Sorting[AccountSortProperty]],
    Depends(SortingGetter(AccountSortProperty, ["created_at"])),
]
