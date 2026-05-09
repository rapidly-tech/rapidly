"""Sort-order enum and dependency for payment list queries.

Provides ``ListSorting`` as a FastAPI dependency that parses
``?sorting=-created_at`` query parameters into typed sort descriptors.
"""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class PaymentSortProperty(StrEnum):
    created_at = "created_at"
    status = "status"
    amount = "amount"
    method = "method"


_DEFAULT_ORDER: list[str] = ["-created_at"]

type ListSorting = Annotated[
    list[Sorting[PaymentSortProperty]],
    Depends(SortingGetter(PaymentSortProperty, _DEFAULT_ORDER)),
]
