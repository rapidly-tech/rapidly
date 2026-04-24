"""Tests for ``rapidly/identity/oauth2/metadata.py``.

``get_server_metadata`` produces the OIDC discovery document served
at ``/.well-known/openid-configuration``. Every OAuth2/OIDC client
library bootstraps by reading this — drift surfaces as silent
misrouting (wrong token endpoint, missing jwks, etc.).

Pins:
- RFC 8414 required fields (``issuer``, ``authorization_endpoint``,
  ``token_endpoint``, ``jwks_uri``) — missing any = discovery fails
- OpenIDProviderMetadata adds ``userinfo_endpoint`` +
  ``subject_types_supported`` + ``id_token_signing_alg_values_supported``
  as required
- ``get_server_metadata`` resolves endpoints via ``url_for`` with the
  documented route names (``oauth2:request_token``, ``oauth2:userinfo``,
  ``oauth2:revoke_token``, ``oauth2:introspect_token``,
  ``oauth2:create_client``, ``well_known.jwks``)
- ``authorization_endpoint`` is built from ``FRONTEND_BASE_URL``,
  not url_for — pinned so a refactor doesn't silently route the
  consent screen through the API host
- ``scopes_supported`` = module-level ``SCOPES_SUPPORTED`` (excludes
  reserved browser-only scopes)
- Static constants flow through (``issuer`` = constants.ISSUER,
  ``claims_supported`` = constants.CLAIMS_SUPPORTED, etc.)
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from rapidly.config import settings
from rapidly.identity.auth.scope import SCOPES_SUPPORTED
from rapidly.identity.oauth2 import constants
from rapidly.identity.oauth2.authorization_server import AuthorizationServer
from rapidly.identity.oauth2.metadata import (
    OAuth2AuthorizationServerMetadata,
    OpenIDProviderMetadata,
    get_server_metadata,
)


class TestOAuth2ServerMetadataRequired:
    def test_required_rfc8414_fields(self) -> None:
        body = OAuth2AuthorizationServerMetadata(
            issuer="https://x",
            authorization_endpoint="https://x/authorize",
            token_endpoint="https://x/token",
            jwks_uri="https://x/jwks",
            scopes_supported=["openid"],
            response_types_supported=["code"],
        )
        assert body.issuer == "https://x"

    @pytest.mark.parametrize(
        "missing",
        [
            "issuer",
            "authorization_endpoint",
            "token_endpoint",
            "jwks_uri",
            "scopes_supported",
            "response_types_supported",
        ],
    )
    def test_each_required_field_is_enforced(self, missing: str) -> None:
        from pydantic import ValidationError

        body: dict[str, Any] = {
            "issuer": "https://x",
            "authorization_endpoint": "https://x/a",
            "token_endpoint": "https://x/t",
            "jwks_uri": "https://x/j",
            "scopes_supported": ["openid"],
            "response_types_supported": ["code"],
        }
        del body[missing]
        with pytest.raises(ValidationError):
            OAuth2AuthorizationServerMetadata.model_validate(body)


class TestOpenIDProviderMetadataRequired:
    @pytest.mark.parametrize(
        "missing",
        [
            "userinfo_endpoint",
            "subject_types_supported",
            "id_token_signing_alg_values_supported",
        ],
    )
    def test_openid_required_additions(self, missing: str) -> None:
        from pydantic import ValidationError

        body: dict[str, Any] = {
            "issuer": "https://x",
            "authorization_endpoint": "https://x/a",
            "token_endpoint": "https://x/t",
            "jwks_uri": "https://x/j",
            "scopes_supported": ["openid"],
            "response_types_supported": ["code"],
            "userinfo_endpoint": "https://x/userinfo",
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
        }
        del body[missing]
        with pytest.raises(ValidationError):
            OpenIDProviderMetadata.model_validate(body)


class TestGetServerMetadata:
    def _stub_server(self) -> AuthorizationServer:
        # ``get_server_metadata`` reads ~6 attributes off the
        # server; a SimpleNamespace lets the test stay DB-free.
        return cast(
            "AuthorizationServer",
            SimpleNamespace(
                response_types_supported=["code"],
                response_modes_supported=["query"],
                grant_types_supported=["authorization_code", "refresh_token"],
                token_endpoint_auth_methods_supported=["client_secret_post"],
                revocation_endpoint_auth_methods_supported=["client_secret_post"],
                introspection_endpoint_auth_methods_supported=["client_secret_post"],
                code_challenge_methods_supported=["S256"],
            ),
        )

    def _url_for(self, name: str) -> str:
        # Captures the documented route names so the test pins the
        # exact mapping.
        return f"https://api.rapidly.tech/_url_for/{name}"

    def test_issuer_is_constants_issuer(self) -> None:
        meta = get_server_metadata(self._stub_server(), self._url_for)
        assert meta.issuer == constants.ISSUER

    def test_authorization_endpoint_uses_frontend_base_url(self) -> None:
        # Load-bearing pin: the consent screen lives on the
        # frontend origin, NOT the API origin. A refactor that
        # routed this through url_for would silently send users
        # to an endpoint that doesn't render the consent UI.
        meta = get_server_metadata(self._stub_server(), self._url_for)
        assert meta.authorization_endpoint == (
            f"{settings.FRONTEND_BASE_URL}/oauth2/authorize"
        )
        assert "_url_for" not in meta.authorization_endpoint

    @pytest.mark.parametrize(
        ("field", "route_name"),
        [
            ("token_endpoint", "oauth2:request_token"),
            ("jwks_uri", "well_known.jwks"),
            ("userinfo_endpoint", "oauth2:userinfo"),
            ("registration_endpoint", "oauth2:create_client"),
            ("revocation_endpoint", "oauth2:revoke_token"),
            ("introspection_endpoint", "oauth2:introspect_token"),
        ],
    )
    def test_endpoint_uses_documented_route_name(
        self, field: str, route_name: str
    ) -> None:
        # Pin each endpoint → route-name mapping so a refactor
        # that renames a route can't silently point the discovery
        # doc at a non-existent URL.
        meta = get_server_metadata(self._stub_server(), self._url_for)
        assert getattr(meta, field) == self._url_for(route_name)

    def test_scopes_supported_excludes_reserved(self) -> None:
        # ``SCOPES_SUPPORTED`` is already filtered to exclude
        # browser-only scopes (web:read / web:write) — the
        # discovery doc must never advertise those to third-party
        # clients.
        meta = get_server_metadata(self._stub_server(), self._url_for)
        assert meta.scopes_supported == SCOPES_SUPPORTED
        assert "web:read" not in meta.scopes_supported
        assert "web:write" not in meta.scopes_supported

    def test_constants_flow_through(self) -> None:
        meta = get_server_metadata(self._stub_server(), self._url_for)
        assert meta.service_documentation == constants.SERVICE_DOCUMENTATION
        assert meta.subject_types_supported == constants.SUBJECT_TYPES_SUPPORTED
        assert meta.id_token_signing_alg_values_supported == (
            constants.ID_TOKEN_SIGNING_ALG_VALUES_SUPPORTED
        )
        assert meta.claims_supported == constants.CLAIMS_SUPPORTED
