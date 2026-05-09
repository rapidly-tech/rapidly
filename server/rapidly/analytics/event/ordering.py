"""Ordering definitions for the analytics event module.

Declares the sortable columns available on event-related list endpoints
and provides pre-built FastAPI dependency aliases for each query type.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter

# ── Event timeline ordering ──────────────────────────────────────────


class EventSortProperty(StrEnum):
    """Columns available for sorting raw event records."""

    timestamp = "timestamp"


type ListSorting = Annotated[
    list[Sorting[EventSortProperty]],
    Depends(SortingGetter(EventSortProperty, ["-timestamp"])),
]


# ── Aggregated event-name ordering ───────────────────────────────────


class EventNamesSortProperty(StrEnum):
    """Columns available for sorting the event-names aggregation."""

    last_seen = "last_seen"
    first_seen = "first_seen"
    occurrences = "occurrences"
    event_name = "name"  # `name` is a reserved word, so we use `event_name`


type EventNamesSorting = Annotated[
    list[Sorting[EventNamesSortProperty]],
    Depends(SortingGetter(EventNamesSortProperty, ["-last_seen"])),
]


# ── Statistical breakdown ordering ───────────────────────────────────


class EventStatisticsSortProperty(StrEnum):
    """Columns available for sorting event statistics."""

    total = "total"
    occurrences = "occurrences"
    average = "average"
    p95 = "p95"
    p99 = "p99"
    event_name = "name"  # `name` is a reserved word, so we use `event_name`


type EventStatisticsSorting = Annotated[
    list[Sorting[EventStatisticsSortProperty]],
    Depends(SortingGetter(EventStatisticsSortProperty, ["-total"])),
]
