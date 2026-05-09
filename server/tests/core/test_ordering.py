"""Tests for ``rapidly/core/ordering.py`` — the ``?sorting=`` query
parameter parser that backs every paginated list endpoint.

Contracts pinned:
- ``-<name>`` prefix → descending
- Bare ``<name>`` → ascending
- Unknown criterion names → ``RequestValidationError`` with a
  ``("query", "sorting")`` location
- ``None`` input falls back to the default-sorting list supplied at
  construction time
- Multi-column ordering preserved in input order
"""

from __future__ import annotations

from enum import StrEnum

import pytest

from rapidly.core.ordering import SortingGetter
from rapidly.errors import RequestValidationError


class _TestSortProperty(StrEnum):
    __test__ = False  # don't collect this as a pytest test class
    created_at = "created_at"
    name = "name"
    priority = "priority"


@pytest.mark.asyncio
class TestSortingGetter:
    async def test_ascending_criterion_parses_with_descending_false(self) -> None:
        getter = SortingGetter(_TestSortProperty, ["-created_at"])
        result = await getter(["name"])
        assert result == [(_TestSortProperty.name, False)]

    async def test_descending_criterion_uses_minus_prefix(self) -> None:
        getter = SortingGetter(_TestSortProperty, ["-created_at"])
        result = await getter(["-created_at"])
        assert result == [(_TestSortProperty.created_at, True)]

    async def test_preserves_multi_column_order(self) -> None:
        getter = SortingGetter(_TestSortProperty, [])
        result = await getter(["name", "-created_at", "priority"])
        assert result == [
            (_TestSortProperty.name, False),
            (_TestSortProperty.created_at, True),
            (_TestSortProperty.priority, False),
        ]

    async def test_none_falls_back_to_the_default(self) -> None:
        getter = SortingGetter(_TestSortProperty, ["-created_at"])
        result = await getter(None)
        assert result == [(_TestSortProperty.created_at, True)]

    async def test_empty_list_is_not_the_same_as_none(self) -> None:
        # Empty list short-circuits to an empty parsed list (no default
        # fallback triggered). This distinguishes "no sorting" from
        # "sorting not supplied".
        getter = SortingGetter(_TestSortProperty, ["-created_at"])
        result = await getter([])
        assert result == []

    async def test_rejects_unknown_criterion_name(self) -> None:
        getter = SortingGetter(_TestSortProperty, [])
        with pytest.raises(RequestValidationError):
            await getter(["unknown_field"])

    async def test_rejects_unknown_criterion_with_minus_prefix(self) -> None:
        # The minus is stripped BEFORE enum validation, so `-bogus` must
        # still fail on the enum check.
        getter = SortingGetter(_TestSortProperty, [])
        with pytest.raises(RequestValidationError):
            await getter(["-bogus"])

    async def test_error_carries_query_sorting_loc(self) -> None:
        # OpenAPI error consumers key on ``loc`` — pin the exact shape.
        getter = SortingGetter(_TestSortProperty, [])
        try:
            await getter(["bogus"])
            raise AssertionError("expected RequestValidationError")
        except RequestValidationError as err:
            errors = err.errors()
            assert len(errors) == 1
            assert errors[0]["loc"] == ("query", "sorting")
            assert errors[0]["input"] == "bogus"

    async def test_empty_string_input_rejected(self) -> None:
        # Empty string is not a valid enum member.
        getter = SortingGetter(_TestSortProperty, [])
        with pytest.raises(RequestValidationError):
            await getter([""])

    async def test_bare_minus_rejected(self) -> None:
        # A bare "-" strips to "" which isn't a valid enum member.
        getter = SortingGetter(_TestSortProperty, [])
        with pytest.raises(RequestValidationError):
            await getter(["-"])

    async def test_same_field_asc_and_desc_both_parse(self) -> None:
        # An unusual but valid input — tests that the parser handles
        # the same field twice (even if the DB wouldn't typically order
        # that way).
        getter = SortingGetter(_TestSortProperty, [])
        result = await getter(["name", "-name"])
        assert result == [
            (_TestSortProperty.name, False),
            (_TestSortProperty.name, True),
        ]
