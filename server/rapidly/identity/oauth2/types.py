"""Pydantic schemas for OAuth2 / OIDC endpoints.

Defines request and response models for client registration,
authorization, token exchange, introspection, revocation, and
the OIDC UserInfo payload.
"""

import ipaddress
import re
from typing import Annotated, Any, Literal

from fastapi.openapi.constants import REF_TEMPLATE
from pydantic import (
    UUID4,
    AfterValidator,
    AnyUrl,
    BeforeValidator,
    Discriminator,
    EmailStr,
    Field,
    HttpUrl,
    TypeAdapter,
)

from rapidly.core.types import AuditableSchema, Schema
from rapidly.identity.auth.scope import (
    SCOPES_SUPPORTED,
    SCOPES_SUPPORTED_DISPLAY_NAMES,
    Scope,
    scope_to_list,
)

from .sub_type import SubType

# ---------------------------------------------------------------------------
# Redirect URI validation
# ---------------------------------------------------------------------------

_LOCALHOST_PATTERN = re.compile(
    r"^([a-z0-9\-]+\.)?localhost(\d+)?$", flags=re.IGNORECASE
)


def _host_is_private_network(host: str) -> bool:
    """Return True for RFC-1918 addresses and localhost variants."""
    try:
        addr = ipaddress.IPv4Address(host)
        return addr.is_private
    except ValueError:
        return bool(_LOCALHOST_PATTERN.match(host))


def _validate_redirect_uri_scheme(uri: HttpUrl) -> HttpUrl:
    """Reject plain HTTP redirect URIs unless targeting a local address."""
    if uri.scheme == "http":
        if uri.host is None or not _host_is_private_network(uri.host):
            raise ValueError("An HTTPS URL is required.")
    return uri


URIOrLocalhost = Annotated[AnyUrl, AfterValidator(_validate_redirect_uri_scheme)]
Scopes = Annotated[list[Scope], BeforeValidator(scope_to_list)]


# ---------------------------------------------------------------------------
# Client configuration
# ---------------------------------------------------------------------------


class OAuth2ClientConfiguration(Schema):
    """Fields accepted when registering or updating an OAuth2 client."""

    client_name: str
    redirect_uris: list[URIOrLocalhost]
    token_endpoint_auth_method: Literal[
        "client_secret_basic", "client_secret_post", "none"
    ] = "client_secret_post"
    grant_types: list[Literal["authorization_code", "refresh_token"]] = [
        "authorization_code",
        "refresh_token",
    ]
    response_types: list[Literal["code"]] = ["code"]
    scope: str = " ".join(SCOPES_SUPPORTED)
    client_uri: str | None = None
    logo_uri: HttpUrl | None = None
    tos_uri: HttpUrl | None = None
    policy_uri: HttpUrl | None = None
    default_sub_type: SubType = SubType.workspace


class OAuth2ClientConfigurationUpdate(Schema):
    """All fields optional for partial updates."""

    client_id: str | None = None
    client_name: str | None = None
    redirect_uris: list[URIOrLocalhost] | None = None
    token_endpoint_auth_method: (
        Literal["client_secret_basic", "client_secret_post", "none"] | None
    ) = None
    grant_types: list[Literal["authorization_code", "refresh_token"]] | None = None
    response_types: list[Literal["code"]] | None = None
    scope: str | None = None
    client_uri: str | None = None
    logo_uri: HttpUrl | None = None
    tos_uri: HttpUrl | None = None
    policy_uri: HttpUrl | None = None
    default_sub_type: SubType | None = None


class OAuth2Client(AuditableSchema, OAuth2ClientConfiguration):
    client_id: str
    client_secret: str
    client_id_issued_at: int
    client_secret_expires_at: int


class OAuth2ClientPublic(AuditableSchema):
    """Subset of client fields safe for display during the consent screen."""

    client_id: str
    client_name: str | None
    client_uri: str | None
    logo_uri: str | None
    tos_uri: str | None
    policy_uri: str | None


# ---------------------------------------------------------------------------
# Authorization response
# ---------------------------------------------------------------------------


class AuthorizeUser(Schema):
    id: UUID4
    email: EmailStr
    avatar_url: str | None


class AuthorizeWorkspace(Schema):
    id: UUID4
    slug: str
    avatar_url: str | None


class AuthorizeResponseBase(Schema):
    client: OAuth2ClientPublic
    sub_type: SubType
    sub: AuthorizeUser | AuthorizeWorkspace | None
    scopes: Scopes
    scope_display_names: dict[str, str] = Field(
        default={s.value: label for s, label in SCOPES_SUPPORTED_DISPLAY_NAMES.items()}
    )


class AuthorizeResponseUser(AuthorizeResponseBase):
    sub_type: Literal[SubType.user]
    sub: AuthorizeUser | None


class AuthorizeResponseWorkspace(AuthorizeResponseBase):
    sub_type: Literal[SubType.workspace]
    sub: AuthorizeWorkspace | None
    workspaces: list[AuthorizeWorkspace]


AuthorizeResponse = Annotated[
    AuthorizeResponseUser | AuthorizeResponseWorkspace,
    Discriminator(discriminator="sub_type"),
]

authorize_response_adapter: TypeAdapter[AuthorizeResponse] = TypeAdapter(
    AuthorizeResponse
)


# ---------------------------------------------------------------------------
# Token exchange
# ---------------------------------------------------------------------------


class TokenRequestBase(Schema):
    """Shared fields for all token-exchange grant types."""

    grant_type: Literal["authorization_code", "refresh_token", "web"]
    client_id: str
    client_secret: str


class AuthorizationCodeTokenRequest(TokenRequestBase):
    grant_type: Literal["authorization_code"]
    code: str
    redirect_uri: HttpUrl


class RefreshTokenRequest(TokenRequestBase):
    grant_type: Literal["refresh_token"]
    refresh_token: str


class WebTokenRequest(TokenRequestBase):
    grant_type: Literal["web"]
    session_token: str
    sub_type: Literal["user", "workspace"] = Field(default="user")
    sub: UUID4 | None = None
    scope: str | None = Field(default=None)


class TokenResponse(Schema):
    access_token: str
    token_type: Literal["Bearer"]
    expires_in: int
    refresh_token: str | None
    scope: str
    id_token: str


# ---------------------------------------------------------------------------
# Revocation
# ---------------------------------------------------------------------------


class RevokeTokenRequest(Schema):
    token: str
    token_type_hint: Literal["access_token", "refresh_token"] | None = None
    client_id: str
    client_secret: str


class RevokeTokenResponse(Schema): ...


# ---------------------------------------------------------------------------
# Introspection
# ---------------------------------------------------------------------------


class IntrospectTokenRequest(Schema):
    token: str
    token_type_hint: Literal["access_token", "refresh_token"] | None = None
    client_id: str
    client_secret: str


class IntrospectTokenResponse(Schema):
    active: bool
    client_id: str
    token_type: Literal["access_token", "refresh_token"]
    scope: str
    sub_type: SubType
    sub: str
    aud: str
    iss: str
    exp: int
    iat: int


# ---------------------------------------------------------------------------
# UserInfo
# ---------------------------------------------------------------------------


class UserInfoUser(Schema):
    sub: str
    name: str | None = None
    email: str | None = None
    email_verified: bool | None = None


class UserInfoWorkspace(Schema):
    sub: str
    name: str | None = None


UserInfo = UserInfoUser | UserInfoWorkspace


# ---------------------------------------------------------------------------
# OpenAPI form-schema injection
# ---------------------------------------------------------------------------

_FORM_ENCODED_MODELS: tuple[type[Schema], ...] = (
    AuthorizationCodeTokenRequest,
    RefreshTokenRequest,
    WebTokenRequest,
    RevokeTokenRequest,
    IntrospectTokenRequest,
)


def add_oauth2_form_schemas(openapi_schema: dict[str, Any]) -> dict[str, Any]:
    """Register form-encoded request schemas that FastAPI cannot auto-detect."""
    components = openapi_schema["components"]["schemas"]
    for model_cls in _FORM_ENCODED_MODELS:
        components[model_cls.__name__] = model_cls.model_json_schema(
            ref_template=REF_TEMPLATE
        )
    return openapi_schema
