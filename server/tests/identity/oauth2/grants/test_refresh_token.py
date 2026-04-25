"""Tests for ``rapidly/identity/oauth2/grants/refresh_token.py``.

Refresh-token grant with rotation. Three load-bearing surfaces:

- ``INCLUDE_NEW_REFRESH_TOKEN = True`` — refresh-token ROTATION.
  Drift to False would let a refresh token be reused indefinitely
  (no-rotation = high replay risk if a token is leaked).
- ``TOKEN_ENDPOINT_AUTH_METHODS`` accepts the three documented
  methods: ``client_secret_basic``, ``client_secret_post``, and
  ``none`` (for public PKCE clients). Drift would either lock
  out confidential clients or open up an unauthenticated path
  for confidential ones.
- ``authenticate_refresh_token`` hashes the incoming token via
  ``get_token_hash`` BEFORE the DB lookup. Drift to plain-text
  comparison would mean a DB compromise leaks raw refresh
  tokens. Revoked tokens return None even if the hash matches —
  defends against rotation-replay.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from rapidly.identity.oauth2.grants.refresh_token import RefreshTokenGrant


class TestGrantConfiguration:
    def test_includes_new_refresh_token(self) -> None:
        # Pin: refresh-token rotation. Drift to False would let a
        # leaked refresh token be reused indefinitely.
        assert RefreshTokenGrant.INCLUDE_NEW_REFRESH_TOKEN is True

    def test_accepts_three_auth_methods(self) -> None:
        # Pin the three documented endpoint-auth methods. Drift
        # could either lock out confidential clients or open an
        # unauthenticated path for them.
        assert RefreshTokenGrant.TOKEN_ENDPOINT_AUTH_METHODS == [
            "client_secret_basic",
            "client_secret_post",
            "none",
        ]


def _grant_with_record(record: Any | None) -> RefreshTokenGrant:
    """Build a grant instance whose session.execute returns *record*."""
    grant = RefreshTokenGrant.__new__(RefreshTokenGrant)
    server = MagicMock()
    session = MagicMock()
    result = MagicMock()
    result.unique = MagicMock(return_value=result)
    result.scalar_one_or_none = MagicMock(return_value=record)
    session.execute = MagicMock(return_value=result)
    server.session = session
    grant.server = server
    return grant


class TestAuthenticateRefreshToken:
    def test_hashes_token_before_lookup(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # LOAD-BEARING SECURITY: incoming raw refresh token is
        # hashed via get_token_hash BEFORE the DB query. Drift to
        # plain-text storage would mean a DB compromise leaks
        # raw refresh tokens that could authenticate against
        # unrotated copies.
        captured: dict[str, str] = {}

        from rapidly.identity.oauth2.grants import refresh_token as rt

        def fake_hash(token: str, *, secret: str) -> str:
            captured["token"] = token
            captured["secret"] = secret
            return "HASHED:" + token

        monkeypatch.setattr(rt, "get_token_hash", fake_hash)

        record = MagicMock()
        record.is_revoked = MagicMock(return_value=False)
        grant = _grant_with_record(record)

        result = grant.authenticate_refresh_token("rapidly_rt_user_abc")
        assert result is record
        assert captured["token"] == "rapidly_rt_user_abc"

    def test_returns_none_when_token_unknown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from rapidly.identity.oauth2.grants import refresh_token as rt

        monkeypatch.setattr(rt, "get_token_hash", lambda t, *, secret: "h")

        grant = _grant_with_record(None)
        assert grant.authenticate_refresh_token("unknown") is None

    def test_returns_none_when_token_revoked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin (security): a revoked refresh token MUST NOT
        # re-authenticate even if its hash still resolves in the
        # DB. Defends against rotation-replay where an attacker
        # captures a refresh token before rotation flushes.
        from rapidly.identity.oauth2.grants import refresh_token as rt

        monkeypatch.setattr(rt, "get_token_hash", lambda t, *, secret: "h")

        revoked = MagicMock()
        revoked.is_revoked = MagicMock(return_value=True)
        grant = _grant_with_record(revoked)
        assert grant.authenticate_refresh_token("anything") is None


class TestAuthenticateUser:
    def test_returns_token_sub_type_value(self) -> None:
        # Pin: the user identity is taken from the token's
        # ``get_sub_type_value()`` method. Drift to a different
        # method would let the grant return the wrong subject
        # (privilege confusion).
        token = MagicMock()
        sentinel = object()
        token.get_sub_type_value = MagicMock(return_value=sentinel)
        grant = RefreshTokenGrant.__new__(RefreshTokenGrant)
        assert grant.authenticate_user(token) is sentinel


class TestRevokeOldCredential:
    def test_sets_revoked_at_and_flushes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: ``revoke_old_credential`` sets ``refresh_token_revoked_at``
        # to the CURRENT epoch and flushes the session immediately.
        # Drift to a deferred flush would let a parallel token
        # request use the about-to-be-revoked token.
        monkeypatch.setattr(
            "rapidly.identity.oauth2.grants.refresh_token.time.time",
            lambda: 1700000000.0,
        )

        token = MagicMock()
        grant = RefreshTokenGrant.__new__(RefreshTokenGrant)
        grant.server = MagicMock()
        grant.server.session = MagicMock()

        grant.revoke_old_credential(token)

        # Pin: integer epoch (NOT float).
        assert token.refresh_token_revoked_at == 1700000000
        # Pin: session.flush invoked so the revocation is visible
        # to concurrent reads.
        grant.server.session.add.assert_called_once_with(token)
        grant.server.session.flush.assert_called_once()
