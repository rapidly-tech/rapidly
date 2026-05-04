"""Tests for ``rapidly/integrations/apple/actions.py``.

Apple Sign-In integration. Four load-bearing surfaces:

- Exception hierarchy: ``AppleServiceError`` extends
  ``RapidlyError``; ``CannotLinkUnverifiedEmailError`` and
  ``AccountLinkedToAnotherUserError`` use status code 403 (the
  frontend's account-merge UX branches on 403). Drift to 400 would
  blank out the special handling.
- ``get_apple_oauth_client(secret=True)`` MUST emit a JWT signed
  with **ES256** carrying:
  * issuer (``iss``) = ``APPLE_TEAM_ID``
  * audience (``aud``) = ``https://appleid.apple.com``
  * subject (``sub``) = ``APPLE_CLIENT_ID``
  * ``exp`` = ``iat + 3600`` (1 hour, the Apple-spec maximum)
  * header ``kid`` = ``APPLE_KEY_ID``
  Any drift here makes Apple reject every token-exchange.
- ``get_apple_oauth_client(secret=False)`` returns an OpenID client
  with empty client_secret (used for read-only metadata calls).
  Both modes wire through the SAME Apple discovery URL +
  ``["openid", "email"]`` base scopes.
- ``_decode_profile`` validates id_token with **RS256** (NOT ES256
  — that's for the OUTGOING client_secret), audience pinned to
  ``APPLE_CLIENT_ID``, issuer pinned to ``https://appleid.apple.com``.
  Drift in any of these would either accept forged tokens or
  reject every legitimate sign-in.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import jwt
import pytest

from rapidly.errors import RapidlyError
from rapidly.integrations.apple.actions import (
    AccountLinkedToAnotherUserError,
    AppleServiceError,
    CannotLinkUnverifiedEmailError,
    _decode_profile,
    get_apple_oauth_client,
)


class TestExceptionHierarchy:
    def test_apple_service_error_extends_rapidly_error(self) -> None:
        # Pin: callers in the OAuth handler catch on the base class
        # to render a generic OAuth-failure response.
        assert issubclass(AppleServiceError, RapidlyError)

    def test_cannot_link_extends_service_error(self) -> None:
        assert issubclass(CannotLinkUnverifiedEmailError, AppleServiceError)

    def test_account_linked_extends_service_error(self) -> None:
        assert issubclass(AccountLinkedToAnotherUserError, AppleServiceError)


class TestCannotLinkUnverifiedEmailError:
    def test_includes_email_in_message(self) -> None:
        # Pin: the email is interpolated so the user knows which
        # account is conflicting. Drift to a generic message
        # would force a support ticket.
        err = CannotLinkUnverifiedEmailError(email="alice@privaterelay.appleid.com")
        assert "alice@privaterelay.appleid.com" in str(err)

    def test_uses_status_code_403(self) -> None:
        # Pin: the frontend's account-merge UX branches on 403.
        err = CannotLinkUnverifiedEmailError(email="x@y.com")
        assert err.status_code == 403


class TestAccountLinkedToAnotherUserError:
    def test_uses_status_code_403(self) -> None:
        err = AccountLinkedToAnotherUserError()
        assert err.status_code == 403


class TestGetAppleOAuthClientNoSecret:
    def test_returns_openid_client_with_empty_secret(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the no-secret form returns an OpenID client with
        # empty client_secret — used for read-only metadata calls
        # that don't need the signed assertion.
        client = get_apple_oauth_client(secret=False)
        # OpenID client stores client_secret on the instance.
        assert getattr(client, "client_secret", None) == ""


class TestGetAppleOAuthClientWithSecret:
    def _set_apple_settings(self, monkeypatch: pytest.MonkeyPatch) -> str:
        # Set up minimal Apple settings + a real ES256 PEM key.
        # The actual signing test does NOT require us to verify
        # signatures — only to confirm the JWT structure.
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        # Generate a throw-away P-256 (ES256) key for the test.
        key = ec.generate_private_key(ec.SECP256R1())
        pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("ascii")

        from rapidly.config import settings as settings_obj

        monkeypatch.setattr(settings_obj, "APPLE_TEAM_ID", "TEAM12345")
        monkeypatch.setattr(settings_obj, "APPLE_CLIENT_ID", "com.example.app")
        monkeypatch.setattr(settings_obj, "APPLE_KEY_ID", "KEYABCDEF")
        monkeypatch.setattr(settings_obj, "APPLE_KEY_VALUE", pem)
        return pem

    def test_jwt_uses_es256_algorithm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: ES256 (NOT RS256). Apple REJECTS any other alg for
        # the client_secret JWT. Drift would silently break every
        # token-exchange.
        self._set_apple_settings(monkeypatch)
        client = get_apple_oauth_client(secret=True)
        secret = getattr(client, "client_secret", "")
        assert secret  # non-empty
        header = jwt.get_unverified_header(secret)
        assert header["alg"] == "ES256"

    def test_jwt_header_carries_apple_key_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: ``kid`` header is REQUIRED by Apple to look up the
        # right public key — without it every signature
        # verification fails on Apple's side.
        self._set_apple_settings(monkeypatch)
        client = get_apple_oauth_client(secret=True)
        secret = getattr(client, "client_secret", "")
        header = jwt.get_unverified_header(secret)
        assert header["kid"] == "KEYABCDEF"

    def test_jwt_claims_match_apple_spec(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: Apple's documented client_secret JWT claim set:
        # iss = team id, sub = client id, aud = appleid issuer.
        # Mis-mapping would Apple-reject every token request.
        self._set_apple_settings(monkeypatch)
        client = get_apple_oauth_client(secret=True)
        secret = getattr(client, "client_secret", "")
        # ``options={"verify_signature": False}`` — we don't have
        # the matching public key, only the structure matters.
        claims = jwt.decode(secret, options={"verify_signature": False})
        assert claims["iss"] == "TEAM12345"
        assert claims["aud"] == "https://appleid.apple.com"
        assert claims["sub"] == "com.example.app"

    def test_jwt_expires_one_hour_after_issue(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: ``exp = iat + 3600`` — Apple caps client_secret
        # JWTs at 6 months but our convention is 1 hour for
        # rotation safety. Drift to a much longer window weakens
        # rotation; drift shorter would expire mid-flow.
        self._set_apple_settings(monkeypatch)
        client = get_apple_oauth_client(secret=True)
        secret = getattr(client, "client_secret", "")
        claims = jwt.decode(secret, options={"verify_signature": False})
        assert claims["exp"] - claims["iat"] == 3600

    def test_openid_discovery_url_pinned(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin the discovery endpoint URL passed to the OpenID
        # constructor so a regression to a typo'd path silently
        # makes every Apple sign-in fail at the OIDC config-fetch
        # step. Capture by monkeypatching the OpenID class.
        from rapidly.integrations.apple import actions as M

        captured: dict[str, Any] = {}

        class _FakeOpenID:
            def __init__(
                self,
                client_id: str,
                client_secret: str,
                openid_configuration_endpoint: str,
                base_scopes: Any = None,
            ) -> None:
                captured["url"] = openid_configuration_endpoint
                captured["base_scopes"] = base_scopes

        monkeypatch.setattr(M, "OpenID", _FakeOpenID)
        get_apple_oauth_client(secret=False)
        assert (
            captured["url"]
            == "https://appleid.apple.com/.well-known/openid-configuration"
        )
        # Pin the requested scopes — Apple sign-in requires
        # ``openid`` (always) and we additionally request
        # ``email`` to populate the user record.
        assert captured["base_scopes"] == ["openid", "email"]


class TestDecodeProfile:
    def test_uses_rs256_algorithm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: id_token verification uses RS256 (Apple's signing
        # alg for id_tokens). NOT ES256 (that's our outgoing
        # client_secret). Drift here would either accept forged
        # tokens (alg=none) or reject every legitimate sign-in.
        decoded_payload = {
            "sub": "001234.abc",
            "email": "user@privaterelay.appleid.com",
            "email_verified": True,
        }

        captured: dict[str, Any] = {}

        def fake_decode(
            token: str, *, key: Any = None, algorithms: Any = None, **kwargs: Any
        ) -> dict[str, Any]:
            captured["algorithms"] = algorithms
            captured["audience"] = kwargs.get("audience")
            captured["issuer"] = kwargs.get("issuer")
            return decoded_payload

        with (
            patch(
                "rapidly.integrations.apple.actions.jwt.decode",
                side_effect=fake_decode,
            ),
            patch(
                "rapidly.integrations.apple.actions.jwks_client.get_signing_key_from_jwt",
                return_value=MagicMock(),
            ),
        ):
            import asyncio

            result = asyncio.run(_decode_profile("fake-id-token"))

        assert captured["algorithms"] == ["RS256"]
        assert captured["issuer"] == "https://appleid.apple.com"
        # Audience matches APPLE_CLIENT_ID (read at call time).
        from rapidly.config import settings as settings_obj

        assert captured["audience"] == settings_obj.APPLE_CLIENT_ID
        # Returned payload pulls the documented Apple JWT claims.
        assert result["id"] == "001234.abc"
        assert result["email"] == "user@privaterelay.appleid.com"
        assert result["email_verified"] is True

    def test_returns_typeddict_with_three_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin the profile shape: id, email, email_verified — and
        # nothing else. Apple does NOT provide display_name or
        # picture for sign-in (privacy-by-design). Drift that
        # added optional fields would silently re-shape callers.
        with (
            patch(
                "rapidly.integrations.apple.actions.jwt.decode",
                return_value={
                    "sub": "abc",
                    "email": "a@b.com",
                    "email_verified": False,
                },
            ),
            patch(
                "rapidly.integrations.apple.actions.jwks_client.get_signing_key_from_jwt",
                return_value=MagicMock(),
            ),
        ):
            import asyncio

            result = asyncio.run(_decode_profile("token"))

        assert set(result.keys()) == {"id", "email", "email_verified"}
        assert result["email_verified"] is False
