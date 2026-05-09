"""Tests for ``rapidly/identity/auth/routing.py``.

Focuses on ``_build_scopes_section`` — the pure Markdown-snippet
generator that enriches each authenticated endpoint's OpenAPI
description with the scope list required to call it.

Security-adjacent invariant: **reserved scopes** (``web:read``,
``web:write``) are filtered out before emission so they never leak
into the public OpenAPI spec — third-party OAuth clients shouldn't
see that those scopes exist at all.
"""

from __future__ import annotations

from rapidly.identity.auth.routing import _build_scopes_section
from rapidly.identity.auth.scope import Scope


class TestBuildScopesSection:
    def test_returns_empty_string_when_no_scopes_supplied(self) -> None:
        assert _build_scopes_section(None) == ""
        assert _build_scopes_section(set()) == ""

    def test_returns_empty_when_all_scopes_are_reserved(self) -> None:
        # If the only required scopes are reserved, the OpenAPI
        # section stays empty — we never expose reserved scopes to
        # third parties.
        result = _build_scopes_section({Scope.web_read, Scope.web_write})
        assert result == ""

    def test_formats_single_scope_with_markdown_backticks(self) -> None:
        result = _build_scopes_section({Scope.file_sharing_read})
        assert result == "\n\n**Scopes**: `file_sharing:read`"

    def test_sorts_multiple_scopes_alphabetically(self) -> None:
        # Sort order is documented (``sorted(...)``) — pinning so a
        # refactor to insertion order doesn't break API-docs
        # consistency across builds.
        result = _build_scopes_section(
            {Scope.file_sharing_write, Scope.file_sharing_read, Scope.openid}
        )
        # Expected alphabetical: file_sharing:read < file_sharing:write < openid
        assert (
            result
            == "\n\n**Scopes**: `file_sharing:read` `file_sharing:write` `openid`"
        )

    def test_strips_reserved_scopes_from_mixed_input(self) -> None:
        # A mixed input (reserved + non-reserved) keeps only the
        # non-reserved scopes — the reserved ones are filtered out
        # before rendering.
        result = _build_scopes_section(
            {Scope.web_read, Scope.file_sharing_read, Scope.web_write}
        )
        assert "web:read" not in result
        assert "web:write" not in result
        assert "`file_sharing:read`" in result

    def test_leading_double_newline_separates_from_endpoint_description(
        self,
    ) -> None:
        # The ``\n\n`` prefix creates a Markdown paragraph break so the
        # Scopes section renders as its own section in the OpenAPI
        # docs rather than tacking onto the endpoint summary.
        result = _build_scopes_section({Scope.file_sharing_read})
        assert result.startswith("\n\n**Scopes**: ")

    def test_each_scope_is_wrapped_in_individual_backticks(self) -> None:
        # Pinning ``` `x` `y` ``` rather than ```` ``x, y`` ```` — the
        # inline-code format is what renders correctly in Mintlify /
        # ReDoc / Swagger UI.
        result = _build_scopes_section({Scope.openid, Scope.profile})
        # No comma between scopes, no leading backtick-sequence.
        assert "," not in result
        # Each scope appears exactly once wrapped in backticks.
        assert result.count("`openid`") == 1
        assert result.count("`profile`") == 1
