"""Ordering definitions for the custom-field module.

Provides the sortable column enum and a ready-made FastAPI dependency
for custom-field list queries.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class CustomFieldSortProperty(StrEnum):
    """Columns that custom-field lists can be sorted by."""

    slug = "slug"
    custom_field_name = (
        "name"  # `name` is a reserved word, so we use `custom_field_name`
    )
    type = "type"
    created_at = "created_at"


type ListSorting = Annotated[
    list[Sorting[CustomFieldSortProperty]],
    Depends(SortingGetter(CustomFieldSortProperty, ["slug"])),
]
