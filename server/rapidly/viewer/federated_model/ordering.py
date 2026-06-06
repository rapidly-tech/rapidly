"""Sort-order enum for federated-model list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class FederatedModelSortProperty(StrEnum):
    name = "name"
    created_at = "created_at"
    status = "status"


_DEFAULT_ORDER: list[str] = ["-created_at"]

type FederatedModelsSorting = Annotated[
    list[Sorting[FederatedModelSortProperty]],
    Depends(SortingGetter(FederatedModelSortProperty, _DEFAULT_ORDER)),
]
