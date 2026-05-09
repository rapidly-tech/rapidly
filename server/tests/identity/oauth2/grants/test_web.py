"""Tests for ``rapidly/identity/oauth2/grants/web.py``.

First-party ``grant_type=web`` exchange. Five load-bearing surfaces:

- ``GRANT_TYPE = "web"`` and ``TOKEN_ENDPOINT_AUTH_METHODS`` carry
  ``client_secret_basic`` / ``client_secret_post`` ONLY (NOT
  ``"none"`` like the refresh-token grant). The ``web`` flow is
  for first-party confidential clients (the dashboard backend);
  drift to allow ``none`` would let any anonymous caller mint
  access tokens from a stolen session cookie.
- ``_verify_session_token`` hashes the session token via
  ``get_token_hash`` before DB lookup AND filters
  ``expires_at > now_utc()``. Drift in either would expose raw
  tokens (DB compromise) or accept stale sessions.
- ``sub_type`` parameter rules: defaults to ``user`` when
  omitted; ``workspace`` requires ``sub``; ``user`` forbids
  ``sub`` (privilege-confusion defence — without it, a workspace-
  scoped token could be minted under user sub_type).
- ``_resolve_subject`` for ``workspace`` sub_type requires the
  user to hold an active (NOT soft-deleted) membership in that
  workspace. Drift to skip the membership check would let any
  user mint tokens for any workspace.
- Missing session_token → InvalidRequestError; expired/unknown
  session → InvalidGrantError. The two error types are
  documented in RFC 6749; drift would break OAuth2-spec compliance.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from authlib.oauth2.rfc6749.errors import (
    InvalidGrantError,
    InvalidRequestError,
    UnauthorizedClientError,
)

from rapidly.identity.oauth2.grants.web import WebGrant
from rapidly.identity.oauth2.sub_type import SubType


class TestGrantConfiguration:
    def test_grant_type_pinned(self) -> None:
        # Pin: the grant_type literal that clients submit. Drift
        # would silently break first-party dashboard auth.
        assert WebGrant.GRANT_TYPE == "web"

    def test_no_none_auth_method(self) -> None:
        # LOAD-BEARING SECURITY: only confidential-client methods
        # are allowed. Drift to include "none" would let any
        # anonymous caller mint access tokens from a stolen
        # session cookie.
        assert "none" not in WebGrant.TOKEN_ENDPOINT_AUTH_METHODS
        assert WebGrant.TOKEN_ENDPOINT_AUTH_METHODS == [
            "client_secret_basic",
            "client_secret_post",
        ]


def _grant_with_payload(
    *,
    payload_data: dict[str, Any],
    session_record: Any | None = None,
    workspace: Any | None = None,
) -> WebGrant:
    """Build a WebGrant whose request.payload + server.session yield given values."""
    grant = WebGrant.__new__(WebGrant)
    request = MagicMock()
    payload = MagicMock()
    payload.data = payload_data
    payload.scope = payload_data.get("scope", "")
    request.payload = payload
    grant.request = request

    server = MagicMock()
    sess = MagicMock()

    # First call returns session_record, second call returns workspace.
    results: list[MagicMock] = []
    for value in (session_record, workspace):
        result = MagicMock()
        result.unique = MagicMock(return_value=result)
        result.scalar_one_or_none = MagicMock(return_value=value)
        results.append(result)
    sess.execute = MagicMock(side_effect=results)
    server.session = sess
    grant.server = server
    return grant


class TestVerifyClient:
    def test_unauthorized_client_when_grant_not_allowed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: a client without the ``web`` grant type configured
        # is REJECTED. Drift would let any registered OAuth2
        # client mint web-grant tokens.
        client = MagicMock()
        client.check_grant_type = MagicMock(return_value=False)

        grant = WebGrant.__new__(WebGrant)
        grant.authenticate_token_endpoint_client = MagicMock(return_value=client)

        with pytest.raises(UnauthorizedClientError):
            grant._verify_client()

    def test_returns_client_when_grant_allowed(self) -> None:
        client = MagicMock()
        client.check_grant_type = MagicMock(return_value=True)

        grant = WebGrant.__new__(WebGrant)
        grant.authenticate_token_endpoint_client = MagicMock(return_value=client)
        assert grant._verify_client() is client


class TestVerifySessionTokenValidation:
    def test_missing_session_token_raises_invalid_request(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: a missing session_token field is a RFC 6749
        # ``invalid_request`` error (NOT invalid_grant).
        grant = _grant_with_payload(payload_data={})
        with pytest.raises(InvalidRequestError):
            grant._verify_session_token(client=MagicMock())

    def test_invalid_sub_type_raises_invalid_request(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        grant = _grant_with_payload(
            payload_data={"session_token": "rapidly_us_x", "sub_type": "weird"}
        )
        with pytest.raises(InvalidRequestError):
            grant._verify_session_token(client=MagicMock())

    def test_workspace_subtype_requires_sub(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: workspace sub_type without ``sub`` raises. Drift
        # would let workspace-scoped tokens be minted without
        # specifying which workspace.
        grant = _grant_with_payload(
            payload_data={
                "session_token": "rapidly_us_x",
                "sub_type": SubType.workspace.value,
            }
        )
        with pytest.raises(InvalidRequestError):
            grant._verify_session_token(client=MagicMock())

    def test_user_subtype_forbids_sub(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # LOAD-BEARING SECURITY: providing ``sub`` with
        # sub_type=user is rejected. Drift would let an attacker
        # smuggle workspace-scope into a user-scope token (privilege
        # confusion).
        grant = _grant_with_payload(
            payload_data={
                "session_token": "rapidly_us_x",
                "sub_type": SubType.user.value,
                "sub": str(uuid4()),
            }
        )
        with pytest.raises(InvalidRequestError):
            grant._verify_session_token(client=MagicMock())

    def test_session_hashed_before_db_lookup(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # LOAD-BEARING SECURITY: raw session token is hashed via
        # get_token_hash BEFORE the DB lookup. Drift to plain-text
        # storage would mean a DB compromise leaks raw tokens.
        from rapidly.identity.oauth2.grants import web as M

        captured: dict[str, str] = {}

        def fake_hash(token: str, *, secret: str) -> str:
            captured["token"] = token
            return "HASHED:" + token

        monkeypatch.setattr(M, "get_token_hash", fake_hash)

        # Build a session record that resolves cleanly.
        session_record = MagicMock()
        session_record.user = MagicMock()
        grant = _grant_with_payload(
            payload_data={"session_token": "rapidly_us_xyz"},
            session_record=session_record,
        )
        # Avoid scope validation for this test.
        grant.server.validate_requested_scope = MagicMock(return_value=None)
        result = grant._verify_session_token(client=MagicMock())
        assert captured["token"] == "rapidly_us_xyz"
        # Resolved subject is the session's user (sub_type=user default).
        assert result == (SubType.user, session_record.user)

    def test_unknown_session_raises_invalid_grant(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: missing session row → InvalidGrantError (NOT
        # invalid_request). RFC 6749 distinguishes the two; drift
        # would break OAuth2-spec compliance.
        from rapidly.identity.oauth2.grants import web as M

        monkeypatch.setattr(M, "get_token_hash", lambda t, *, secret: "h")

        grant = _grant_with_payload(
            payload_data={"session_token": "rapidly_us_x"},
            session_record=None,
        )
        with pytest.raises(InvalidGrantError):
            grant._verify_session_token(client=MagicMock())


class TestResolveSubjectUser:
    def test_user_subtype_returns_session_user(self) -> None:
        # Pin: user sub_type returns (SubType.user, session.user).
        grant = WebGrant.__new__(WebGrant)
        user = MagicMock()
        result = grant._resolve_subject(SubType.user, raw_sub=None, user=user)
        assert result == (SubType.user, user)


class TestResolveSubjectWorkspace:
    def test_invalid_uuid_raises_invalid_request(self) -> None:
        # Pin: malformed sub UUID is invalid_request, not
        # invalid_grant.
        grant = WebGrant.__new__(WebGrant)
        with pytest.raises(InvalidRequestError):
            grant._resolve_subject(
                SubType.workspace, raw_sub="not-a-uuid", user=MagicMock()
            )

    def test_no_membership_raises_invalid_grant(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # LOAD-BEARING SECURITY: a user requesting a workspace
        # token MUST hold an active membership. Drift would let
        # any user mint tokens for any workspace.
        grant = WebGrant.__new__(WebGrant)
        grant.server = MagicMock()
        result = MagicMock()
        result.unique = MagicMock(return_value=result)
        result.scalar_one_or_none = MagicMock(return_value=None)
        grant.server.session = MagicMock()
        grant.server.session.execute = MagicMock(return_value=result)

        with pytest.raises(InvalidGrantError):
            grant._resolve_subject(
                SubType.workspace, raw_sub=str(uuid4()), user=MagicMock()
            )

    def test_with_membership_returns_workspace(self) -> None:
        # Pin: with an active membership, returns
        # (SubType.workspace, workspace).
        grant = WebGrant.__new__(WebGrant)
        workspace = MagicMock()
        result = MagicMock()
        result.unique = MagicMock(return_value=result)
        result.scalar_one_or_none = MagicMock(return_value=workspace)
        grant.server = MagicMock()
        grant.server.session = MagicMock()
        grant.server.session.execute = MagicMock(return_value=result)

        sub_type, subject = grant._resolve_subject(
            SubType.workspace, raw_sub=str(uuid4()), user=MagicMock()
        )
        assert sub_type == SubType.workspace
        assert subject is workspace
