"""Sort-order enums for module-member + module-link list endpoints."""

from enum import StrEnum
from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter


class ModuleExtrasSortProperty(StrEnum):
    created_at = "created_at"


_DEFAULT_ORDER: list[str] = ["-created_at"]

type ModuleExtrasSorting = Annotated[
    list[Sorting[ModuleExtrasSortProperty]],
    Depends(SortingGetter(ModuleExtrasSortProperty, _DEFAULT_ORDER)),
]
