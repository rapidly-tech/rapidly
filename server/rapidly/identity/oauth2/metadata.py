"""OpenID Connect / OAuth2 discovery metadata (RFC 8414).

Builds the JSON document served at ``/.well-known/openid-configuration``
describing the authorization server's endpoints, supported grant types,
scopes, signing algorithms, and other capabilities.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING

from pydantic import BaseModel

from rapidly.config import settings
from rapidly.identity.auth.scope import SCOPES_SUPPORTED

from . import constants

if TYPE_CHECKING:
    from .authorization_server import AuthorizationServer


# ---------------------------------------------------------------------------
# RFC 8414 -- OAuth 2.0 Authorization Server Metadata
# ---------------------------------------------------------------------------


class OAuth2AuthorizationServerMetadata(BaseModel):
    """Core fields defined by RFC 8414."""

    # Required endpoints
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str

    # Optional endpoints
    registration_endpoint: str | None = None
    revocation_endpoint: str | None = None
    introspection_endpoint: str | None = None

    # Capabilities
    scopes_supported: list[str]
    response_types_supported: list[str]
    response_modes_supported: list[str] | None = None
    grant_types_supported: list[str] | None = None

    # Auth methods
    token_endpoint_auth_methods_supported: list[str] | None = None
    token_endpoint_auth_signing_alg_values_supported: list[str] | None = None
    revocation_endpoint_auth_methods_supported: list[str] | None = None
    revocation_endpoint_auth_signing_alg_values_supported: list[str] | None = None
    introspection_endpoint_auth_methods_supported: list[str] | None = None
    introspection_endpoint_auth_signing_alg_values_supported: list[str] | None = None

    # Human-readable links
    service_documentation: str | None = None
    op_policy_uri: str | None = None
    op_tos_uri: str | None = None

    # Miscellaneous
    ui_locales_supported: list[str] | None = None
    code_challenge_methods_supported: list[str] | None = None


# ---------------------------------------------------------------------------
# OpenID Connect Discovery 1.0 -- Provider Metadata
# ---------------------------------------------------------------------------


class OpenIDProviderMetadata(OAuth2AuthorizationServerMetadata):
    """Extended metadata for OpenID Connect providers.

    See: https://openid.net/specs/openid-connect-discovery-1_0.html#ProviderMetadata
    """

    userinfo_endpoint: str

    # Subject
    subject_types_supported: list[str]
    acr_values_supported: list[str] | None = None

    # ID token
    id_token_signing_alg_values_supported: list[str]
    id_token_encryption_alg_values_supported: list[str] | None = None
    id_token_encryption_enc_values_supported: list[str] | None = None

    # UserInfo
    userinfo_signing_alg_values_supported: list[str] | None = None
    userinfo_encryption_alg_values_supported: list[str] | None = None
    userinfo_encryption_enc_values_supported: list[str] | None = None

    # Request objects
    request_object_signing_alg_values_supported: list[str] | None = None
    request_object_encryption_alg_values_supported: list[str] | None = None
    request_object_encryption_enc_values_supported: list[str] | None = None

    # Claims
    claims_supported: list[str] | None = None
    claims_locales_supported: list[str] | None = None
    claim_types_supported: list[str] | None = None
    claims_parameter_supported: bool | None = None

    # Display
    display_values_supported: list[str] | None = None

    # Request URI
    request_parameter_supported: bool | None = None
    request_uri_parameter_supported: bool | None = None
    require_request_uri_registration: bool | None = None


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def get_server_metadata(
    authorization_server: "AuthorizationServer", url_for: Callable[[str], str]
) -> OpenIDProviderMetadata:
    """Assemble the full OIDC discovery document from live server state."""
    return OpenIDProviderMetadata(
        issuer=constants.ISSUER,
        authorization_endpoint=f"{settings.FRONTEND_BASE_URL}/oauth2/authorize",
        token_endpoint=url_for("oauth2:request_token"),
        jwks_uri=url_for("well_known.jwks"),
        userinfo_endpoint=url_for("oauth2:userinfo"),
        registration_endpoint=url_for("oauth2:create_client"),
        revocation_endpoint=url_for("oauth2:revoke_token"),
        introspection_endpoint=url_for("oauth2:introspect_token"),
        scopes_supported=SCOPES_SUPPORTED,
        response_types_supported=authorization_server.response_types_supported,
        response_modes_supported=authorization_server.response_modes_supported,
        grant_types_supported=authorization_server.grant_types_supported,
        token_endpoint_auth_methods_supported=(
            authorization_server.token_endpoint_auth_methods_supported
        ),
        revocation_endpoint_auth_methods_supported=(
            authorization_server.revocation_endpoint_auth_methods_supported
        ),
        introspection_endpoint_auth_methods_supported=(
            authorization_server.introspection_endpoint_auth_methods_supported
        ),
        service_documentation=constants.SERVICE_DOCUMENTATION,
        code_challenge_methods_supported=(
            authorization_server.code_challenge_methods_supported
        ),
        subject_types_supported=constants.SUBJECT_TYPES_SUPPORTED,
        id_token_signing_alg_values_supported=(
            constants.ID_TOKEN_SIGNING_ALG_VALUES_SUPPORTED
        ),
        claims_supported=constants.CLAIMS_SUPPORTED,
    )
