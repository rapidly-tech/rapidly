"""Ordering definitions for the external-event module.

Declares sortable columns for external (inbound webhook) event lists
and provides a pre-built FastAPI dependency alias.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class ExternalEventSortProperty(StrEnum):
    """Columns that external-event lists can be sorted by."""

    source = "source"
    task_name = "task_name"
    created_at = "created_at"
    handled_at = "handled_at"


type ListSorting = Annotated[
    list[Sorting[ExternalEventSortProperty]],
    Depends(SortingGetter(ExternalEventSortProperty, ["-created_at"])),
]
