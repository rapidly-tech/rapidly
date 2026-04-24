"""Tests for ``rapidly/identity/oauth2/types.py``.

The load-bearing surface here is the redirect-URI validator. OAuth2
authorization codes ride back to the client via the ``redirect_uri``,
so accepting ``http://`` on a public host is a MITM-harvested-code
attack class. The validator implements the standard exception: HTTP
is allowed ONLY when the host resolves to a local / RFC-1918 address
(native client loopback, local dev).

Also pins:
- Client-registration defaults (auth method, grant types, response
  types, sub_type) — OAuth2 client libraries read these from the
  returned registration; drift would silently break downstream SDKs
- ``OAuth2ClientPublic`` does NOT leak ``client_secret`` / grants /
  redirect URIs (consent-screen info-leak defence)
- ``TokenResponse.token_type`` is the Literal ``Bearer``
- ``AuthorizeResponse`` dispatches on ``sub_type`` (user/workspace)
- ``_FORM_ENCODED_MODELS`` count pins the five form-encoded schemas
  that must be manually registered in OpenAPI
"""

from __future__ import annotations

from typing import Any, get_args

import pytest
from pydantic import ValidationError

from rapidly.identity.oauth2 import types as T
from rapidly.identity.oauth2.sub_type import SubType
from rapidly.identity.oauth2.types import (
    _FORM_ENCODED_MODELS,
    AuthorizeResponse,
    OAuth2ClientConfiguration,
    OAuth2ClientPublic,
    TokenResponse,
    _host_is_private_network,
    _validate_redirect_uri_scheme,
    add_oauth2_form_schemas,
    authorize_response_adapter,
)

# ── Helpers ──


def _valid_client_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "client_name": "x",
        "redirect_uris": ["https://app.example.com/callback"],
    }
    body.update(overrides)
    return body


# ── Private-network + redirect-URI validator ──


class TestHostIsPrivateNetwork:
    @pytest.mark.parametrize(
        "host",
        [
            "127.0.0.1",
            "10.0.0.1",
            "172.16.0.1",
            "192.168.1.1",
            "localhost",
            "localhost4000",
            "sub.localhost",
        ],
    )
    def test_recognises_local_variants(self, host: str) -> None:
        assert _host_is_private_network(host) is True

    @pytest.mark.parametrize(
        "host",
        [
            "8.8.8.8",
            "1.1.1.1",
            "example.com",
            "api.example.com",
            "local-host",  # NOT localhost — hyphen break pattern? yes it fails _LOCALHOST_PATTERN
        ],
    )
    def test_rejects_public_hosts(self, host: str) -> None:
        assert _host_is_private_network(host) is False


class TestRedirectUriSchemeValidator:
    def test_https_always_accepted(self) -> None:
        from pydantic import HttpUrl

        url = HttpUrl("https://api.example.com/cb")
        assert _validate_redirect_uri_scheme(url) == url

    def test_http_public_host_rejected(self) -> None:
        # Load-bearing OAuth2 security pin. HTTP callback on a public
        # host is an authorization-code interception vector.
        from pydantic import HttpUrl

        with pytest.raises(ValueError, match="HTTPS URL is required"):
            _validate_redirect_uri_scheme(HttpUrl("http://api.example.com/cb"))

    @pytest.mark.parametrize(
        "local_url",
        [
            "http://127.0.0.1:3000/cb",
            "http://localhost:3000/cb",
            "http://192.168.1.2:3000/cb",
            "http://10.0.0.5:3000/cb",
        ],
    )
    def test_http_local_host_accepted(self, local_url: str) -> None:
        # Native client loopback is the RFC-6749 / RFC-8252
        # exception — dev machines and desktop apps can't get a
        # TLS cert for localhost.
        from pydantic import HttpUrl

        _validate_redirect_uri_scheme(HttpUrl(local_url))


class TestClientConfigurationRejectsHttpPublic:
    def test_integration_rejects_http_public_redirect(self) -> None:
        # Wired via ``Annotated[AnyUrl, AfterValidator(...)]``.
        with pytest.raises(ValidationError):
            OAuth2ClientConfiguration(
                **_valid_client_body(redirect_uris=["http://evil.example.com/cb"])
            )

    def test_integration_accepts_http_localhost(self) -> None:
        OAuth2ClientConfiguration(
            **_valid_client_body(redirect_uris=["http://localhost:3000/cb"])
        )


# ── Defaults ──


class TestClientConfigurationDefaults:
    def test_token_endpoint_auth_method_default(self) -> None:
        # Default must stay ``client_secret_post`` — downstream SDKs
        # read this from the registration response to decide how to
        # send credentials on the token endpoint. Flipping to
        # ``client_secret_basic`` would break existing clients that
        # haven't read the new value.
        body = OAuth2ClientConfiguration(**_valid_client_body())
        assert body.token_endpoint_auth_method == "client_secret_post"

    def test_grant_types_default(self) -> None:
        body = OAuth2ClientConfiguration(**_valid_client_body())
        assert body.grant_types == ["authorization_code", "refresh_token"]

    def test_response_types_default(self) -> None:
        body = OAuth2ClientConfiguration(**_valid_client_body())
        assert body.response_types == ["code"]

    def test_default_sub_type_is_workspace(self) -> None:
        # Defaults to ``workspace`` — the common case for Rapidly's
        # OAuth2 apps. A silent flip to ``user`` would send the
        # wrong ``sub`` type in newly-issued access tokens for every
        # client that didn't set the field explicitly.
        body = OAuth2ClientConfiguration(**_valid_client_body())
        assert body.default_sub_type == SubType.workspace


class TestClientConfigurationRejects:
    def test_rejects_unknown_grant_type(self) -> None:
        with pytest.raises(ValidationError):
            OAuth2ClientConfiguration(**_valid_client_body(grant_types=["implicit"]))

    def test_rejects_unknown_response_type(self) -> None:
        with pytest.raises(ValidationError):
            OAuth2ClientConfiguration(**_valid_client_body(response_types=["token"]))

    def test_rejects_unknown_auth_method(self) -> None:
        with pytest.raises(ValidationError):
            OAuth2ClientConfiguration(
                **_valid_client_body(token_endpoint_auth_method="private_key_jwt")
            )


# ── Consent-screen info-leak defence ──


class TestOAuth2ClientPublic:
    def test_does_not_expose_client_secret(self) -> None:
        # Load-bearing pin. This model is what the consent screen
        # renders — leaking ``client_secret`` here would publish it
        # to any user who can reach the consent URL.
        fields = set(OAuth2ClientPublic.model_fields.keys())
        for forbidden in (
            "client_secret",
            "redirect_uris",
            "grant_types",
            "response_types",
            "scope",
            "token_endpoint_auth_method",
        ):
            assert forbidden not in fields

    def test_only_exposes_display_fields(self) -> None:
        # Whitelist the safe surface so silent additions are caught.
        expected = {
            "created_at",
            "modified_at",
            "client_id",
            "client_name",
            "client_uri",
            "logo_uri",
            "tos_uri",
            "policy_uri",
        }
        assert set(OAuth2ClientPublic.model_fields.keys()) == expected


# ── Token response ──


class TestTokenResponse:
    def test_token_type_is_literal_bearer(self) -> None:
        # Spec-level pin: access tokens are always ``Bearer``.
        # Clients parse this literally.
        resp = TokenResponse(
            access_token="a",
            token_type="Bearer",
            expires_in=3600,
            refresh_token=None,
            scope="",
            id_token="id",
        )
        assert resp.token_type == "Bearer"

    def test_rejects_non_bearer_token_type(self) -> None:
        with pytest.raises(ValidationError):
            TokenResponse(
                access_token="a",
                token_type="Mac",  # type: ignore[arg-type]
                expires_in=3600,
                refresh_token=None,
                scope="",
                id_token="id",
            )


# ── Authorize response discriminator ──


class TestAuthorizeResponseDiscriminator:
    def test_dispatches_on_sub_type_user(self) -> None:
        from rapidly.identity.oauth2.types import AuthorizeResponseUser

        body = {
            "client": {
                "id": "11111111-1111-1111-1111-111111111111",
                "created_at": "2026-01-01T00:00:00+00:00",
                "modified_at": "2026-01-01T00:00:00+00:00",
                "client_id": "c",
                "client_name": None,
                "client_uri": None,
                "logo_uri": None,
                "tos_uri": None,
                "policy_uri": None,
            },
            "sub_type": "user",
            "sub": None,
            "scopes": "",
        }
        result = authorize_response_adapter.validate_python(body)
        assert isinstance(result, AuthorizeResponseUser)

    def test_unknown_sub_type_rejected(self) -> None:
        body: dict[str, Any] = {
            "sub_type": "bot",
            "sub": None,
            "scopes": "",
            "client": {},
        }
        with pytest.raises(ValidationError):
            authorize_response_adapter.validate_python(body)

    def test_authorize_response_is_discriminated(self) -> None:
        from pydantic import Discriminator

        metadata = getattr(AuthorizeResponse, "__metadata__", ())
        assert any(isinstance(m, Discriminator) for m in metadata)
        # Exactly 2 variants — user + workspace. A third silently
        # added without wiring the frontend would render the wrong
        # consent screen.
        args = get_args(get_args(AuthorizeResponse)[0])
        assert len(args) == 2


# ── Form-encoded schema registration ──


class TestFormEncodedModelsRegistration:
    def test_pins_the_five_form_encoded_schemas(self) -> None:
        # FastAPI can't auto-discover schemas for form-encoded
        # request bodies — the ``add_oauth2_form_schemas`` helper
        # injects them into the OpenAPI doc. A regression that
        # dropped one would leave the client SDK without a type
        # for that request.
        names = {cls.__name__ for cls in _FORM_ENCODED_MODELS}
        assert names == {
            "AuthorizationCodeTokenRequest",
            "RefreshTokenRequest",
            "WebTokenRequest",
            "RevokeTokenRequest",
            "IntrospectTokenRequest",
        }

    def test_add_oauth2_form_schemas_injects_all_five(self) -> None:
        schema: dict[str, Any] = {"components": {"schemas": {}}}
        result = add_oauth2_form_schemas(schema)
        assert set(result["components"]["schemas"].keys()) == {
            cls.__name__ for cls in _FORM_ENCODED_MODELS
        }


# ── Module surface sanity ──


class TestScopeAlias:
    def test_scopes_runs_through_scope_to_list(self) -> None:
        # ``Scopes = Annotated[list[Scope], BeforeValidator(scope_to_list)]``
        # means a caller can pass a space-separated string and get
        # a parsed list — the OAuth2 spec shape. A regression that
        # dropped the validator would reject every caller using
        # the standard OAuth2 format.

        from pydantic import BeforeValidator

        metadata = getattr(T.Scopes, "__metadata__", ())
        assert any(isinstance(m, BeforeValidator) for m in metadata)
