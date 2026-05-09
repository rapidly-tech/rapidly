"""Extended tests for ``rapidly/core/http.py``.

The existing ``test_http.py`` covers ``get_safe_return_url`` basics.
This file pins:

- ``add_query_parameters`` — merge + override semantics (new params
  win over existing ones; query-free URLs get the query appended;
  fragment is preserved)
- ``_resolve_return_to`` / ``ReturnTo`` Depends wrapper — the
  FastAPI-exposed form of ``get_safe_return_url``
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from rapidly.core.http import _resolve_return_to, add_query_parameters


class TestAddQueryParameters:
    def test_appends_to_urls_with_no_query(self) -> None:
        result = add_query_parameters("https://api.test/path", foo="bar")
        parsed = urlparse(result)
        assert parse_qs(parsed.query) == {"foo": ["bar"]}

    def test_overrides_existing_param(self) -> None:
        # Load-bearing pin: new params WIN over the existing ones.
        # A regression that preferred the existing value would make
        # callers unable to override defaults via this helper.
        result = add_query_parameters("https://api.test/path?foo=old", foo="new")
        parsed = urlparse(result)
        assert parse_qs(parsed.query) == {"foo": ["new"]}

    def test_preserves_unrelated_params(self) -> None:
        result = add_query_parameters("https://api.test/path?keep=1", add="2")
        parsed = urlparse(result)
        assert parse_qs(parsed.query) == {"keep": ["1"], "add": ["2"]}

    def test_list_values_use_doseq_format(self) -> None:
        # ``urlencode(..., doseq=True)`` renders lists as repeated
        # key=value pairs (``?k=a&k=b``), NOT as ``?k=[a,b]`` —
        # the RFC-compliant multi-value form that every HTTP server
        # re-parses correctly.
        result = add_query_parameters("https://api.test/path", k=["a", "b"])
        parsed = urlparse(result)
        assert parse_qs(parsed.query) == {"k": ["a", "b"]}

    def test_preserves_fragment(self) -> None:
        # ``#section`` fragments belong to the URL, not the query.
        # A naive ``?{...}`` concat would strip them.
        result = add_query_parameters("https://api.test/path#section", foo="bar")
        assert result.endswith("#section")

    def test_preserves_path(self) -> None:
        result = add_query_parameters("https://api.test/a/b/c", foo="bar")
        parsed = urlparse(result)
        assert parsed.path == "/a/b/c"


class TestResolveReturnTo:
    @pytest.mark.asyncio
    async def test_none_returns_default_frontend_url(self) -> None:
        # The dependency wrapper delegates to ``get_safe_return_url``.
        # ``None`` resolves to the default frontend path.
        result = await _resolve_return_to(None)
        assert result.startswith("http")

    @pytest.mark.asyncio
    async def test_offsite_sanitised_to_default(self) -> None:
        result = await _resolve_return_to("https://evil.test/steal")
        assert "evil.test" not in result

    @pytest.mark.asyncio
    async def test_allowed_path_preserved(self) -> None:
        result = await _resolve_return_to("/dashboard")
        assert result.endswith("/dashboard")
