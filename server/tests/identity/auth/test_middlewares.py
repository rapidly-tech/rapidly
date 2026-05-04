"""Tests for ``rapidly/identity/auth/middlewares.py``.

Pre-route auth resolution. Three load-bearing surfaces:

- ``get_bearer_token`` parses ``Authorization: Bearer <token>``
  case-insensitively and rejects: missing header, non-Bearer
  scheme, empty token, non-ASCII tokens. Pin: rejecting non-ASCII
  tokens defends against header-smuggling attacks where a UTF-8
  byte sequence could be interpreted differently by upstream
  proxies vs. the app.
- ``_needs_auth`` is the file-sharing self-auth path-based bypass.
  Default-DENY (every path requires auth) UNLESS explicitly
  whitelisted in ``_FILE_SHARING_SELF_AUTH_PATHS``. Segment-aware
  matching: ``/api/file-sharing/signal/`` matches the path
  itself AND ``/api/file-sharing/signal/anything`` BUT NOT
  ``/api/file-sharing/signal-admin``. Drift in the matching
  logic would let an attacker register an endpoint with a
  prefix-collision and bypass auth.
- The whitelist is exactly 3 paths: ``signal``, ``channels``,
  ``ice``. Adding a new path here without security review
  silently disables auth for that endpoint.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from rapidly.identity.auth.middlewares import (
    _BEARER_SCHEME,
    _FILE_SHARING_PREFIX,
    _FILE_SHARING_SELF_AUTH_PATHS,
    _needs_auth,
    get_bearer_token,
)


def _request_with_auth_header(value: str | None) -> Any:
    """Build a minimal Request-like stub with an Authorization header."""
    request = MagicMock()
    request.headers = {"Authorization": value} if value is not None else {}
    return request


class TestBearerScheme:
    def test_pinned_lowercase(self) -> None:
        # Pin: matched lowercase. The scheme comparison in
        # ``get_bearer_token`` does ``.lower() == _BEARER_SCHEME``,
        # so this constant must stay lowercase.
        assert _BEARER_SCHEME == "bearer"


class TestGetBearerToken:
    def test_missing_authorization_header(self) -> None:
        assert get_bearer_token(_request_with_auth_header(None)) is None

    def test_empty_value(self) -> None:
        assert get_bearer_token(_request_with_auth_header("")) is None

    def test_basic_scheme_returns_none(self) -> None:
        # Pin: a Basic auth header is NOT silently treated as
        # Bearer. Drift would let a stolen Basic credential pass
        # as a Bearer token (different DB lookup).
        assert get_bearer_token(_request_with_auth_header("Basic dXNlcjpwYXNz")) is None

    def test_bearer_with_token_extracts_value(self) -> None:
        assert (
            get_bearer_token(_request_with_auth_header("Bearer my-token-abc"))
            == "my-token-abc"
        )

    def test_bearer_case_insensitive(self) -> None:
        # Pin: real-world clients send ``bearer`` / ``BEARER`` /
        # mixed case. Drift to strict case-match would reject ~5%
        # of clients (RFC 6750 §2.1 documents Bearer with capital
        # B but is silent on case-sensitivity).
        for header in ("bearer abc", "Bearer abc", "BEARER abc", "BeArEr abc"):
            assert get_bearer_token(_request_with_auth_header(header)) == "abc"

    def test_non_ascii_token_rejected(self) -> None:
        # Pin (security): non-ASCII tokens are rejected. Defends
        # against header-smuggling where a UTF-8 byte sequence
        # might be normalised differently by an upstream proxy
        # vs. the app — the proxy could pass through a benign
        # byte sequence that normalises to a valid token in the
        # app's view.
        assert get_bearer_token(_request_with_auth_header("Bearer tøken")) is None

    def test_bearer_with_empty_token_rejected(self) -> None:
        # Pin: ``Bearer `` (with no token) → None, NOT empty
        # string. An empty token would otherwise reach the DB
        # lookup with an empty string and might return a stale
        # row.
        assert get_bearer_token(_request_with_auth_header("Bearer ")) is None


class TestFileSharingPrefix:
    def test_prefix_pinned(self) -> None:
        # Pin: the bypass logic targets paths under exactly this
        # prefix. Drift would either expose other modules to the
        # default-anonymous treatment or accidentally route file-
        # sharing through standard auth.
        assert _FILE_SHARING_PREFIX == "/api/file-sharing/"


class TestFileSharingSelfAuthPaths:
    def test_exact_three_paths(self) -> None:
        # Pin the EXACT set. Adding a new entry here MUST be
        # security-reviewed (the path bypasses standard auth).
        # Drift here is a privilege-escalation risk.
        assert _FILE_SHARING_SELF_AUTH_PATHS == (
            "/api/file-sharing/signal/",
            "/api/file-sharing/channels/",
            "/api/file-sharing/ice/",
        )

    def test_all_paths_under_file_sharing_prefix(self) -> None:
        # Pin: every self-auth entry is under the file-sharing
        # prefix. Drift would let a bypass entry leak into
        # other modules.
        for p in _FILE_SHARING_SELF_AUTH_PATHS:
            assert p.startswith(_FILE_SHARING_PREFIX)


class TestNeedsAuthDefaultDeny:
    def test_non_file_sharing_paths_require_auth(self) -> None:
        # Pin: anything outside the file-sharing prefix gets
        # standard auth treatment.
        assert _needs_auth("/api/users/me") is True
        assert _needs_auth("/api/billing/account") is True
        assert _needs_auth("/healthz") is True

    def test_root_path_requires_auth(self) -> None:
        assert _needs_auth("/") is True


class TestNeedsAuthSelfAuthBypass:
    def test_signal_websocket_path_bypasses(self) -> None:
        # Pin: file-sharing signaling WebSocket handles its own
        # auth via the first signaling message.
        assert _needs_auth("/api/file-sharing/signal/abc-123") is False

    def test_channels_path_bypasses(self) -> None:
        assert _needs_auth("/api/file-sharing/channels/xyz/checkout") is False

    def test_ice_path_bypasses(self) -> None:
        assert _needs_auth("/api/file-sharing/ice/abc") is False


class TestNeedsAuthSegmentAwareMatching:
    def test_unknown_file_sharing_subpath_requires_auth(self) -> None:
        # Pin: default-DENY. Any /api/file-sharing/* NOT in the
        # whitelist requires standard auth. Adding a new file-
        # sharing endpoint is safe-by-default — engineers must
        # explicitly add it to _FILE_SHARING_SELF_AUTH_PATHS to
        # opt out.
        assert _needs_auth("/api/file-sharing/sessions") is True
        assert _needs_auth("/api/file-sharing/sessions/list") is True

    def test_segment_collision_requires_auth(self) -> None:
        # Pin (load-bearing security): segment-aware matching.
        # ``/api/file-sharing/signal-admin`` MUST require auth even
        # though its prefix overlaps with ``/api/file-sharing/signal/``.
        # Drift to plain string-prefix match would let an attacker
        # register a ``signal-admin`` endpoint and bypass auth.
        assert _needs_auth("/api/file-sharing/signal-admin") is True
        assert _needs_auth("/api/file-sharing/channels-admin") is True
        assert _needs_auth("/api/file-sharing/ice-config-admin") is True

    def test_self_auth_prefix_match_with_trailing_path(self) -> None:
        # Pin: the trailing slash + any path matches.
        assert _needs_auth("/api/file-sharing/signal/whatever/comes/here") is False

    def test_partial_prefix_outside_file_sharing_requires_auth(self) -> None:
        # Pin: paths that LOOK like file-sharing but aren't
        # under the prefix ALSO require auth.
        assert _needs_auth("/api/file-sharings/signal/x") is True
