"""Sort-order enum and dependency for event type list queries.

Provides ``EventTypesSorting`` as a FastAPI dependency that parses
``?sorting=-last_seen`` query parameters into typed sort descriptors.
"""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class EventTypesSortProperty(StrEnum):
    event_type_name = "name"
    event_type_label = "label"
    occurrences = "occurrences"
    first_seen = "first_seen"
    last_seen = "last_seen"


_DEFAULT_ORDER: list[str] = ["-last_seen"]

type EventTypesSorting = Annotated[
    list[Sorting[EventTypesSortProperty]],
    Depends(SortingGetter(EventTypesSortProperty, _DEFAULT_ORDER)),
]
