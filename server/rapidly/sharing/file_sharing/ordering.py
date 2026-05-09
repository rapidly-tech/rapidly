"""Sorting configuration for file sharing list endpoints."""

from typing import Annotated

from fastapi import Depends

from rapidly.core.ordering import Sorting, SortingGetter

from .pg_repository import FileShareSessionSortProperty

type ListSorting = Annotated[
    list[Sorting[FileShareSessionSortProperty]],
    Depends(SortingGetter(FileShareSessionSortProperty, ["-created_at"])),
]
