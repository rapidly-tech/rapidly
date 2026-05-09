"""Tests for ``rapidly/identity/auth/scope.py`` — the OAuth2 scope enum
and its reserved / supported split.

The ``RESERVED_SCOPES`` set is a security boundary: scopes in this set
must **never** be granted to third-party OAuth clients (they're for
first-party browser sessions only). Pinning which scopes are reserved,
and that they're excluded from ``SCOPES_SUPPORTED`` (the OAuth endpoint
surface), catches accidental privilege escalation by a future refactor.
"""

from __future__ import annotations

import pytest

from rapidly.identity.auth.scope import (
    RESERVED_SCOPES,
    SCOPES_SUPPORTED,
    SCOPES_SUPPORTED_DISPLAY_NAMES,
    Scope,
    scope_to_list,
    scope_to_set,
)


class TestScopeEnum:
    def test_uses_resource_colon_action_convention(self) -> None:
        # Most scopes follow ``resource:action`` (a few OIDC-standard
        # ones are bare). Pinning the shape prevents a refactor that
        # introduces ``resource.action`` or ``resource_action``.
        oidc_standard = {"openid", "profile", "email"}
        for scope in Scope:
            if scope.value in oidc_standard:
                continue
            assert ":" in scope.value, scope.value

    def test_is_a_str_enum_for_direct_string_comparison(self) -> None:
        # StrEnum — scope values compare as strings, which matters for
        # JWT claim parsing and DB queries. Cast to avoid the
        # ``Literal[Scope.x] == Literal["x:y"]`` non-overlap warning.
        assert str(Scope.openid) == "openid"
        assert str(Scope.file_sharing_read) == "file_sharing:read"


class TestReservedScopes:
    def test_contains_web_read_and_web_write(self) -> None:
        # The documented reserved set.
        assert RESERVED_SCOPES == frozenset({Scope.web_read, Scope.web_write})

    def test_is_frozen(self) -> None:
        # A mutable ``set`` could be accidentally extended at runtime.
        assert isinstance(RESERVED_SCOPES, frozenset)


class TestScopesSupported:
    def test_excludes_every_reserved_scope(self) -> None:
        # Security-critical: SCOPES_SUPPORTED is what the OAuth2 client
        # creation form + discovery endpoint advertise. If a reserved
        # scope leaks in, third parties could request ``web_write`` and
        # impersonate a browser session.
        for reserved in RESERVED_SCOPES:
            assert reserved.value not in SCOPES_SUPPORTED

    def test_includes_every_non_reserved_scope(self) -> None:
        non_reserved = {s.value for s in Scope if s not in RESERVED_SCOPES}
        assert set(SCOPES_SUPPORTED) == non_reserved

    def test_count_is_consistent(self) -> None:
        # Reserved + supported = total scopes.
        assert len(SCOPES_SUPPORTED) + len(RESERVED_SCOPES) == len(list(Scope))


class TestDisplayNames:
    def test_every_scope_has_a_display_name(self) -> None:
        # Consent UI relies on this. A new scope without a display
        # would render as a machine name in the consent prompt.
        missing = set(Scope) - set(SCOPES_SUPPORTED_DISPLAY_NAMES.keys())
        assert missing == set(), f"scopes without display name: {missing}"

    def test_no_empty_display_names(self) -> None:
        for scope, display in SCOPES_SUPPORTED_DISPLAY_NAMES.items():
            assert display, f"empty display for {scope}"


class TestScopeToSet:
    def test_parses_single_space_separated_list(self) -> None:
        assert scope_to_set("openid profile email") == {
            Scope.openid,
            Scope.profile,
            Scope.email,
        }

    def test_handles_extra_whitespace(self) -> None:
        assert scope_to_set("  openid   profile  ") == {
            Scope.openid,
            Scope.profile,
        }

    def test_dedupes_repeated_scopes(self) -> None:
        # Set semantics — a ``openid openid openid`` request collapses.
        assert scope_to_set("openid openid") == {Scope.openid}

    def test_empty_string_returns_empty_set(self) -> None:
        assert scope_to_set("") == set()

    def test_rejects_unknown_scope_names(self) -> None:
        with pytest.raises(ValueError, match="totally-fake-scope"):
            scope_to_set("openid totally-fake-scope")


class TestScopeToList:
    def test_returns_a_list_of_Scope_members(self) -> None:
        result = scope_to_list("openid profile")
        assert isinstance(result, list)
        assert set(result) == {Scope.openid, Scope.profile}

    def test_dedupes_via_set_conversion(self) -> None:
        # scope_to_list calls scope_to_set, so duplicates collapse.
        result = scope_to_list("openid openid openid")
        assert len(result) == 1
