"""Sort-order enum for analytic-view list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class AnalyticViewSortProperty(StrEnum):
    name = "name"
    created_at = "created_at"


_DEFAULT_ORDER: list[str] = ["name", "-created_at"]

type AnalyticViewsSorting = Annotated[
    list[Sorting[AnalyticViewSortProperty]],
    Depends(SortingGetter(AnalyticViewSortProperty, _DEFAULT_ORDER)),
]
