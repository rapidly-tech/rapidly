"""Pagination: offset-based and cursor-based list wrappers.

Provides the ``paginate()`` helper for SQLAlchemy queries, the
``PaginatedList`` / ``CursorPaginatedList`` generic response schemas,
and the ``PaginationParamsQuery`` FastAPI dependency.

Design notes
------------
* ``PaginationParams`` is a ``NamedTuple`` so it can be destructured
  directly: ``page, limit = pagination``.
* Both list schemas expose ``data`` / ``meta`` as the canonical
  fields while keeping backward-compatible ``items`` / ``pagination``
  property aliases.
* The ``_resolve_display_name`` helper honours ``ClassName`` metadata
  so that long union types get short names in OpenAPI output.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Annotated, Any, NamedTuple, Self, overload

from fastapi import Depends, Query
from pydantic import BaseModel, GetCoreSchemaHandler
from pydantic._internal._repr import display_as_type
from pydantic_core import CoreSchema
from sqlalchemy import Select, func, over
from sqlalchemy.sql._typing import _ColumnsClauseArgument

from rapidly.config import settings
from rapidly.core.db.models import BaseEntity
from rapidly.core.db.models.base import Model
from rapidly.core.db.postgres import AsyncReadSession
from rapidly.core.types import ClassName, Schema

# ---------------------------------------------------------------------------
# Query-string parameters
# ---------------------------------------------------------------------------


class PaginationParams(NamedTuple):
    """Immutable (page, limit) pair extracted from request query string."""

    page: int
    limit: int


# ---------------------------------------------------------------------------
# Core paginate function
# ---------------------------------------------------------------------------


@overload
async def paginate[RM: BaseEntity](
    session: AsyncReadSession,
    statement: Select[tuple[RM]],
    *,
    pagination: PaginationParams,
    count_clause: _ColumnsClauseArgument[Any] | None = None,
) -> tuple[Sequence[RM], int]: ...


@overload
async def paginate[M: Model](
    session: AsyncReadSession,
    statement: Select[tuple[M]],
    *,
    pagination: PaginationParams,
    count_clause: _ColumnsClauseArgument[Any] | None = None,
) -> tuple[Sequence[M], int]: ...


@overload
async def paginate[T: Any](
    session: AsyncReadSession,
    statement: Select[T],
    *,
    pagination: PaginationParams,
    count_clause: _ColumnsClauseArgument[Any] | None = None,
) -> tuple[Sequence[T], int]: ...


async def paginate(
    session: AsyncReadSession,
    statement: Select[Any],
    *,
    pagination: PaginationParams,
    count_clause: _ColumnsClauseArgument[Any] | None = None,
) -> tuple[Sequence[Any], int]:
    """Execute *statement* with offset/limit and an inline window-function count.

    Returns ``(items, total_count)``.
    """
    page, limit = pagination
    offset = limit * (page - 1)

    counter = count_clause if count_clause is not None else over(func.count())
    counted_stmt = statement.offset(offset).limit(limit).add_columns(counter)

    result = await session.execute(counted_stmt)
    rows = result.unique().all()

    if not rows:
        return [], 0

    items: list[Any] = []
    total = 0
    for row in rows:
        *data_cols, row_total = row._tuple()
        total = int(row_total)
        items.append(data_cols[0] if len(data_cols) == 1 else data_cols)

    return items, total


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def _parse_pagination_params(
    page: int = Query(1, description="Page number, defaults to 1.", gt=0),
    limit: int = Query(
        10,
        description=(
            f"Size of a page, defaults to 10. "
            f"Maximum is {settings.API_PAGINATION_MAX_LIMIT}."
        ),
        gt=0,
    ),
) -> PaginationParams:
    return PaginationParams(page, min(settings.API_PAGINATION_MAX_LIMIT, limit))


# Public alias for external callers
get_pagination_params = _parse_pagination_params

PaginationParamsQuery = Annotated[PaginationParams, Depends(_parse_pagination_params)]


# ---------------------------------------------------------------------------
# Response metadata schemas
# ---------------------------------------------------------------------------


class PageMeta(Schema):
    """Offset-based pagination metadata."""

    total: int
    page: int
    per_page: int
    pages: int


class CursorPagination(Schema):
    """Cursor-based pagination metadata."""

    has_next_page: bool


# ---------------------------------------------------------------------------
# Display-name resolution
# ---------------------------------------------------------------------------


def _resolve_display_name(params: tuple[type[Any], ...]) -> str:
    """Build a comma-separated display name from type params,
    honouring ``ClassName`` metadata annotations."""
    parts: list[str] = []
    for param in params:
        name: str | None = None
        for meta in getattr(param, "__metadata__", ()):
            if isinstance(meta, ClassName):
                name = meta.name
                break
        parts.append(name if name is not None else display_as_type(param))
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Generic paginated response wrappers
# ---------------------------------------------------------------------------


class PaginatedList[T: Any](BaseModel):
    """Offset-paginated list with ``PageMeta`` metadata."""

    data: list[T]
    meta: PageMeta

    @classmethod
    def from_paginated_results(
        cls,
        items: Sequence[T],
        total_count: int,
        pagination_params: PaginationParams,
    ) -> Self:
        page_count = (
            math.ceil(total_count / pagination_params.limit)
            if pagination_params.limit
            else 0
        )
        return cls(
            data=list(items),
            meta=PageMeta(
                total=total_count,
                page=pagination_params.page,
                per_page=pagination_params.limit,
                pages=page_count,
            ),
        )

    @classmethod
    def model_parametrized_name(cls, params: tuple[type[Any], ...]) -> str:
        return f"{cls.__name__}[{_resolve_display_name(params)}]"

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: type[BaseModel], handler: GetCoreSchemaHandler, /
    ) -> CoreSchema:
        result = handler(source)
        result["ref"] = cls.__name__  # type: ignore
        return result

    # Backward-compatible aliases
    @property
    def items(self) -> list[T]:
        return self.data

    @property
    def pagination(self) -> PageMeta:
        return self.meta


class CursorPaginatedList[T: Any](BaseModel):
    """Cursor-paginated list with ``CursorPagination`` metadata."""

    data: list[T]
    meta: CursorPagination

    @classmethod
    def from_results(
        cls,
        items: Sequence[T],
        has_next_page: bool,
    ) -> Self:
        return cls(
            data=list(items),
            meta=CursorPagination(has_next_page=has_next_page),
        )

    @classmethod
    def model_parametrized_name(cls, params: tuple[type[Any], ...]) -> str:
        return f"{cls.__name__}[{_resolve_display_name(params)}]"

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: type[BaseModel], handler: GetCoreSchemaHandler, /
    ) -> CoreSchema:
        result = handler(source)
        result["ref"] = cls.__name__  # type: ignore
        return result

    # Backward-compatible aliases
    @property
    def items(self) -> list[T]:
        return self.data

    @property
    def pagination(self) -> CursorPagination:
        return self.meta
