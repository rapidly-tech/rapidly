"""Tests for ``rapidly/core/pagination.py``.

Pagination is the shared list wrapper for every paginated endpoint in
the API. This file pins the parts that can be exercised without a live
DB or FastAPI request — the param parser's clamp, page-count arithmetic,
``PaginationParams`` NamedTuple destructuring, backward-compat aliases,
and the ``ClassName`` display-name resolver.
"""

from __future__ import annotations

from typing import Annotated

import pytest

from rapidly.config import settings
from rapidly.core.pagination import (
    CursorPaginatedList,
    CursorPagination,
    PageMeta,
    PaginatedList,
    PaginationParams,
    _parse_pagination_params,
    _resolve_display_name,
)
from rapidly.core.types import ClassName


class TestPaginationParams:
    def test_is_namedtuple_destructurable(self) -> None:
        # The module docstring commits to NamedTuple destructuring —
        # callers rely on ``page, limit = pagination``. Pinning it
        # prevents a silent conversion to a regular dataclass that
        # would break every list endpoint.
        p = PaginationParams(page=2, limit=25)
        page, limit = p
        assert page == 2
        assert limit == 25
        assert p.page == 2
        assert p.limit == 25


class TestParsePaginationParams:
    def test_query_defaults_are_1_and_10(self) -> None:
        # FastAPI resolves ``Query(1)`` / ``Query(10)`` at request time —
        # the dependency function cannot be called with no args. Pin
        # the numeric defaults by introspecting the ``Query`` objects
        # so an accidental change to ``Query(5)`` would show up here.
        import inspect

        sig = inspect.signature(_parse_pagination_params)
        assert sig.parameters["page"].default.default == 1
        assert sig.parameters["limit"].default.default == 10

    @pytest.mark.asyncio
    async def test_clamps_limit_to_max(self) -> None:
        # A caller requesting limit=500 must be silently clamped to
        # ``settings.API_PAGINATION_MAX_LIMIT``. The defence is here,
        # not at the query layer — an un-clamped OFFSET+LIMIT would
        # let one request read 10k rows.
        p = await _parse_pagination_params(page=1, limit=10_000)
        assert p.limit == settings.API_PAGINATION_MAX_LIMIT

    @pytest.mark.asyncio
    async def test_preserves_limit_below_max(self) -> None:
        p = await _parse_pagination_params(page=3, limit=7)
        assert p == PaginationParams(page=3, limit=7)


class TestPaginatedListFromResults:
    def test_zero_items_yields_zero_pages(self) -> None:
        result = PaginatedList[int].from_paginated_results(
            [], total_count=0, pagination_params=PaginationParams(page=1, limit=10)
        )
        assert result.data == []
        assert result.meta == PageMeta(total=0, page=1, per_page=10, pages=0)

    def test_exact_division_yields_whole_pages(self) -> None:
        result = PaginatedList[int].from_paginated_results(
            [1, 2, 3],
            total_count=30,
            pagination_params=PaginationParams(page=1, limit=10),
        )
        assert result.meta.pages == 3

    def test_partial_page_rounds_up(self) -> None:
        # 31 items @ 10/page = 4 pages (ceil, not floor). Using floor
        # would hide the last 1-item partial page.
        result = PaginatedList[int].from_paginated_results(
            [1],
            total_count=31,
            pagination_params=PaginationParams(page=1, limit=10),
        )
        assert result.meta.pages == 4

    def test_single_item_yields_single_page(self) -> None:
        result = PaginatedList[int].from_paginated_results(
            [42],
            total_count=1,
            pagination_params=PaginationParams(page=1, limit=10),
        )
        assert result.meta.pages == 1

    def test_backward_compat_aliases(self) -> None:
        # Older call sites use ``.items`` / ``.pagination``; the module
        # docstring documents these as supported. Removing the alias
        # would break a consumer outside the ``data`` / ``meta`` sweep.
        result = PaginatedList[int].from_paginated_results(
            [1, 2],
            total_count=2,
            pagination_params=PaginationParams(page=1, limit=10),
        )
        assert result.items == result.data
        assert result.pagination == result.meta


class TestCursorPaginatedList:
    def test_from_results_roundtrip(self) -> None:
        result = CursorPaginatedList[int].from_results(
            items=[1, 2, 3], has_next_page=True
        )
        assert result.data == [1, 2, 3]
        assert result.meta == CursorPagination(has_next_page=True)

    def test_backward_compat_aliases(self) -> None:
        result = CursorPaginatedList[int].from_results(items=[], has_next_page=False)
        assert result.items == result.data
        assert result.pagination == result.meta


class TestResolveDisplayName:
    def test_uses_classname_metadata_when_present(self) -> None:
        Named = Annotated[int, ClassName("MyShortName")]
        assert _resolve_display_name((Named,)) == "MyShortName"

    def test_falls_back_to_display_as_type(self) -> None:
        assert _resolve_display_name((int,)) == "int"

    def test_joins_multiple_params_with_comma(self) -> None:
        assert _resolve_display_name((int, str)) == "int, str"

    def test_mixes_named_and_unnamed(self) -> None:
        Named = Annotated[int, ClassName("Apple")]
        assert _resolve_display_name((Named, str)) == "Apple, str"
