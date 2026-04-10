"""Ordering definitions for the share module.

Declares sortable columns for share list endpoints and exposes
a pre-wired FastAPI dependency alias.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class ShareSortProperty(StrEnum):
    """Columns that share lists can be sorted by."""

    product_name = "name"  # `name` is a reserved word, so we use `product_name`
    created_at = "created_at"
    price_amount = "price_amount"
    price_amount_type = "price_amount_type"


type ListSorting = Annotated[
    list[Sorting[ShareSortProperty]],
    Depends(SortingGetter(ShareSortProperty, ["-created_at"])),
]
