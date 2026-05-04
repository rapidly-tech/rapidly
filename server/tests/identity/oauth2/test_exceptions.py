"""Tests for ``rapidly/identity/oauth2/exceptions.py``.

RFC 6750 splits Bearer-token errors into two classes:

- ``InvalidTokenError`` — missing / expired / revoked token, HTTP 401
- ``InsufficientScopeError`` — valid credentials but scope is too
  narrow, HTTP **403** (documented distinction from 401)

The module populates both errors' ``realm`` from
``settings.WWW_AUTHENTICATE_REALM`` so the ``WWW-Authenticate`` header
is consistent site-wide. Pinning catches a regression that forgot to
thread the realm through the constructor.

``InsufficientScopeError.required_scopes`` join is **sorted** —
deterministic output is what lets the Authlib SDK parse the scope
parameter reliably.
"""

from __future__ import annotations

from rapidly.config import settings
from rapidly.identity.oauth2.exceptions import (
    InsufficientScopeError,
    InvalidTokenError,
)


class TestInvalidTokenError:
    def test_has_realm_from_settings(self) -> None:
        # A regression that forgot to pass ``realm=_REALM`` would
        # surface as an un-realmed ``WWW-Authenticate`` header —
        # clients with strict parsing would reject the response.
        err = InvalidTokenError("expired")
        headers = err.get_headers()
        auth_header = dict(headers).get("WWW-Authenticate", "")
        assert f'realm="{settings.WWW_AUTHENTICATE_REALM}"' in auth_header

    def test_description_flows_to_headers(self) -> None:
        err = InvalidTokenError("my reason")
        headers = err.get_headers()
        auth_header = dict(headers).get("WWW-Authenticate", "")
        assert "my reason" in auth_header

    def test_passes_extra_kwargs_to_parent(self) -> None:
        # The ``**extra_attributes`` surface lets callers inject
        # additional RFC-6750 fields (e.g. ``error_uri``). A
        # regression dropping the passthrough would silently ignore
        # them.
        err = InvalidTokenError("x", error_uri="https://docs.rapidly.tech/e/42")
        headers = err.get_headers()
        auth_header = dict(headers).get("WWW-Authenticate", "")
        assert "error_uri" in auth_header
        assert "docs.rapidly.tech/e/42" in auth_header


class TestInsufficientScopeError:
    def test_error_is_insufficient_scope(self) -> None:
        # RFC 6750 §3.1 — the ``error`` code must literally be
        # ``insufficient_scope``. Clients dispatch on this string.
        err = InsufficientScopeError(required_scopes={"customer_portal_read"})
        assert err.error == "insufficient_scope"

    def test_status_code_is_403_not_401(self) -> None:
        # Load-bearing distinction: 403 means "authenticated but
        # under-scoped". Returning 401 would make clients drop
        # valid tokens and try to re-authenticate, stalling the
        # user behind a reprompt for credentials they already had.
        err = InsufficientScopeError(required_scopes={"x"})
        assert err.status_code == 403

    def test_description_mentions_higher_privileges(self) -> None:
        # User-facing copy surfaces via generic 403 handlers in
        # older SDKs that don't parse the WWW-Authenticate header.
        err = InsufficientScopeError(required_scopes={"x"})
        assert "higher privileges" in err.description

    def test_scopes_are_joined_sorted(self) -> None:
        # Sorted join is deterministic — lets test fixtures and
        # Authlib SDK consumers cache on the exact string value.
        err = InsufficientScopeError(required_scopes={"zeta", "alpha", "mu"})
        headers = err.get_headers()
        auth_header = dict(headers).get("WWW-Authenticate", "")
        assert 'scope="alpha mu zeta"' in auth_header

    def test_has_realm_from_settings(self) -> None:
        err = InsufficientScopeError(required_scopes={"x"})
        headers = err.get_headers()
        auth_header = dict(headers).get("WWW-Authenticate", "")
        assert f'realm="{settings.WWW_AUTHENTICATE_REALM}"' in auth_header

    def test_single_scope_round_trip(self) -> None:
        # Single-scope case still produces a valid header — no
        # trailing space or quote-adjacency bugs.
        err = InsufficientScopeError(required_scopes={"only_one"})
        headers = err.get_headers()
        auth_header = dict(headers).get("WWW-Authenticate", "")
        assert 'scope="only_one"' in auth_header


class TestInheritance:
    def test_both_inherit_from_invalid_token(self) -> None:
        # The module docstring commits to a parallel inheritance:
        # both errors extend Authlib's ``InvalidTokenError`` base so
        # they share the ``get_headers`` logic that builds the
        # WWW-Authenticate value.
        from authlib.oauth2.rfc6750 import (
            InvalidTokenError as _BaseInvalidToken,
        )

        assert issubclass(InvalidTokenError, _BaseInvalidToken)
        assert issubclass(InsufficientScopeError, _BaseInvalidToken)


class TestExports:
    def test_all_declared(self) -> None:
        from rapidly.identity.oauth2 import exceptions as E

        assert set(E.__all__) == {"InsufficientScopeError", "InvalidTokenError"}
