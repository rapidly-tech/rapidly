"""Ordering definitions for the customer module.

Declares sortable columns for customer list endpoints and provides
a pre-built FastAPI dependency alias.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class CustomerSortProperty(StrEnum):
    """Columns that customer lists can be sorted by."""

    email = "email"
    customer_name = "name"  # `name` is a reserved word, so we use `customer_name`
    created_at = "created_at"


type ListSorting = Annotated[
    list[Sorting[CustomerSortProperty]],
    Depends(SortingGetter(CustomerSortProperty, ["-created_at"])),
]
