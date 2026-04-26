"""Tests for the helpers in
``rapidly/identity/oauth2/authorization_server.py``.

Three load-bearing surfaces:

- ``_strip_public_client_secrets`` removes ``client_secret`` and
  ``client_secret_expires_at`` from the body when
  ``token_endpoint_auth_method == "none"`` (RFC 7591 public
  clients). Drift would leak a transient client_secret to a
  public client that has no use for it (and expects to never
  hold one).
- ``_strip_public_client_secrets`` is a NO-OP for confidential
  clients (any other auth method). Drift to always-strip would
  break confidential-client registration entirely.
- ``_TokenLookupMixin.query_token`` hashes the bearer string
  via ``get_token_hash`` BEFORE looking it up; with a
  ``token_type_hint`` of ``access_token`` it matches the
  ``access_token`` column only, with ``refresh_token`` it
  matches the refresh column only, and with no hint it OR-s
  both columns.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from rapidly.identity.oauth2.authorization_server import (
    _strip_public_client_secrets,
    _TokenLookupMixin,
)


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


class TestStripPublicClientSecrets:
    def test_public_client_secrets_are_stripped(self) -> None:
        # Pin: ``token_endpoint_auth_method == "none"`` (the
        # documented RFC 7591 marker for public clients) →
        # secret fields removed from the body. Drift would leak
        # a transient secret to a client that has no use for it.
        body: dict[str, Any] = {
            "client_id": "abc",
            "client_secret": "shhhh",
            "client_secret_expires_at": 1234567,
            "token_endpoint_auth_method": "none",
        }
        _strip_public_client_secrets(body)
        assert "client_secret" not in body
        assert "client_secret_expires_at" not in body
        # client_id is preserved.
        assert body["client_id"] == "abc"

    def test_confidential_client_keeps_secrets(self) -> None:
        # Pin: any auth method other than ``"none"`` is
        # confidential — secrets MUST stay in the registration
        # response. Drift to always-strip would break
        # confidential-client registration entirely.
        body: dict[str, Any] = {
            "client_id": "abc",
            "client_secret": "shhhh",
            "client_secret_expires_at": 1234567,
            "token_endpoint_auth_method": "client_secret_basic",
        }
        _strip_public_client_secrets(body)
        assert body["client_secret"] == "shhhh"
        assert body["client_secret_expires_at"] == 1234567

    def test_missing_auth_method_is_treated_as_confidential(self) -> None:
        # Pin: when the body doesn't carry the auth method key,
        # the function does NOT strip secrets (defaults to the
        # safe-for-confidential-client branch).
        body: dict[str, Any] = {
            "client_id": "abc",
            "client_secret": "shhhh",
        }
        _strip_public_client_secrets(body)
        assert body["client_secret"] == "shhhh"


class TestTokenLookupMixinQueryToken:
    def _setup(self, monkeypatch: Any) -> tuple[Any, dict[str, Any]]:
        captured: dict[str, Any] = {}

        # Stub get_token_hash to expose what we hashed.
        def _fake_hash(token: str, *, secret: str) -> str:
            captured["raw"] = token
            return f"hashed:{token}"

        monkeypatch.setattr(
            "rapidly.identity.oauth2.authorization_server.get_token_hash",
            _fake_hash,
        )

        instance = _TokenLookupMixin()
        instance.server = MagicMock()
        # Capture the executed statement.
        execute_mock = MagicMock()
        execute_mock.return_value.unique.return_value.scalar_one_or_none.return_value = None

        def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            return execute_mock.return_value

        instance.server.session.execute.side_effect = _exec
        return instance, captured

    def test_hashes_bearer_before_lookup(self, monkeypatch: Any) -> None:
        # Pin: ``get_token_hash`` is applied. Drift to compare
        # raw bearer to stored hash would break every revocation
        # / introspection call.
        instance, captured = self._setup(monkeypatch)
        instance.query_token("rapidly_oat_xyz", None)
        assert captured["raw"] == "rapidly_oat_xyz"

    def test_access_token_hint_filters_access_column_only(
        self, monkeypatch: Any
    ) -> None:
        # Pin: hint=access_token → match only the access_token
        # column. Drift to OR both would let an access-token
        # introspection accidentally surface the matching
        # refresh-token row's metadata.
        instance, captured = self._setup(monkeypatch)
        instance.query_token("xyz", "access_token")

        sql = _compile(captured["stmt"]).lower()
        # Compiled SQL splits the WHERE onto its own line.
        where_fragment = sql.split("where", 1)[1]
        assert "oauth2_tokens.access_token = 'hashed:xyz'" in where_fragment
        assert "refresh_token" not in where_fragment

    def test_refresh_token_hint_filters_refresh_column_only(
        self, monkeypatch: Any
    ) -> None:
        instance, captured = self._setup(monkeypatch)
        instance.query_token("xyz", "refresh_token")

        sql = _compile(captured["stmt"]).lower()
        # Compiled SQL splits the WHERE onto its own line.
        where_fragment = sql.split("where", 1)[1]
        assert "oauth2_tokens.refresh_token = 'hashed:xyz'" in where_fragment
        assert "access_token =" not in where_fragment

    def test_no_hint_or_combines_both_columns(self, monkeypatch: Any) -> None:
        # Pin: no hint → OR both columns. Drift to drop one would
        # let a token-introspection request without a hint fail
        # to find half the tokens (e.g. legitimate access tokens
        # would 404 if only refresh_token were searched).
        instance, captured = self._setup(monkeypatch)
        instance.query_token("xyz", None)

        sql = _compile(captured["stmt"]).lower()
        assert "oauth2_tokens.access_token = 'hashed:xyz'" in sql
        assert "oauth2_tokens.refresh_token = 'hashed:xyz'" in sql
        assert " or " in sql
