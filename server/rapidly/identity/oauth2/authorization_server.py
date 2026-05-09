"""Rapidly OAuth2 / OIDC authorization server.

Integrates Authlib's ``AuthorizationServer`` with:
  - Rapidly's sync SQLAlchemy session (used by Authlib's synchronous grant flow)
  - Prefixed, HMAC-hashed token storage
  - JWK-based signing
  - RFC 7009 revocation, RFC 7662 introspection
  - RFC 7591 / 7592 dynamic client registration and configuration
"""

import json
import secrets
import time
import typing

import structlog
from authlib.oauth2 import AuthorizationServer as _AuthorizationServer
from authlib.oauth2 import OAuth2Error
from authlib.oauth2.rfc6749.errors import UnsupportedResponseTypeError
from authlib.oauth2.rfc6750 import BearerTokenGenerator
from authlib.oauth2.rfc7009 import RevocationEndpoint as _RevocationEndpoint
from authlib.oauth2.rfc7591 import (
    ClientRegistrationEndpoint as _ClientRegistrationEndpoint,
)
from authlib.oauth2.rfc7592 import (
    ClientConfigurationEndpoint as _ClientConfigurationEndpoint,
)
from authlib.oauth2.rfc7662 import IntrospectionEndpoint as _IntrospectionEndpoint
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import Response

from rapidly.config import settings
from rapidly.core.crypto import generate_token, get_token_hash
from rapidly.identity.auth.scope import Scope
from rapidly.identity.oauth2.sub_type import SubTypeValue
from rapidly.logging import Logger
from rapidly.models import OAuth2Client, OAuth2Token, User

from .actions.oauth2_grant import oauth2_grant as oauth2_grant_service
from .constants import (
    ACCESS_TOKEN_PREFIX,
    CLIENT_ID_PREFIX,
    CLIENT_REGISTRATION_TOKEN_PREFIX,
    CLIENT_SECRET_PREFIX,
    ISSUER,
    REFRESH_TOKEN_PREFIX,
)
from .grants import AuthorizationCodeGrant, CodeChallenge, register_grants
from .metadata import get_server_metadata
from .requests import StarletteJsonRequest, StarletteOAuth2Request

_log: Logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_metadata_dict(server: "AuthorizationServer") -> dict[str, typing.Any]:
    """Return server metadata as a plain dict (for endpoint classes)."""
    return get_server_metadata(server, lambda name: name).model_dump(exclude_unset=True)


def _strip_public_client_secrets(body: dict[str, typing.Any]) -> None:
    """Remove secret-related fields when the client uses ``token_endpoint_auth_method=none``."""
    if body.get("token_endpoint_auth_method") == "none":
        body.pop("client_secret", None)
        body.pop("client_secret_expires_at", None)


# ---------------------------------------------------------------------------
# Token lookup mixin (shared by Revocation and Introspection endpoints)
# ---------------------------------------------------------------------------


class _TokenLookupMixin:
    """Resolve an opaque token string to a stored ``OAuth2Token``."""

    server: "AuthorizationServer"

    def query_token(
        self,
        token_string: str,
        token_type_hint: typing.Literal["access_token", "refresh_token"] | None,
    ) -> OAuth2Token | None:
        hashed = get_token_hash(token_string, secret=settings.SECRET)
        stmt = select(OAuth2Token)
        if token_type_hint == "access_token":
            stmt = stmt.where(OAuth2Token.access_token == hashed)
        elif token_type_hint == "refresh_token":
            stmt = stmt.where(OAuth2Token.refresh_token == hashed)
        else:
            stmt = stmt.where(
                or_(
                    OAuth2Token.access_token == hashed,
                    OAuth2Token.refresh_token == hashed,
                )
            )
        return self.server.session.execute(stmt).unique().scalar_one_or_none()


# ---------------------------------------------------------------------------
# RFC 7009 -- Token Revocation
# ---------------------------------------------------------------------------


class RevocationEndpoint(_TokenLookupMixin, _RevocationEndpoint):
    CLIENT_AUTH_METHODS = ["client_secret_basic", "client_secret_post"]

    def revoke_token(self, token: OAuth2Token, request: StarletteOAuth2Request) -> None:
        epoch_now = int(time.time())
        token.access_token_revoked_at = epoch_now  # pyright: ignore
        hint = request.form.get("token_type_hint")
        if hint != "access_token":
            token.refresh_token_revoked_at = epoch_now  # pyright: ignore
        self.server.session.add(token)
        self.server.session.flush()


# ---------------------------------------------------------------------------
# RFC 7662 -- Token Introspection
# ---------------------------------------------------------------------------


class IntrospectionEndpoint(_TokenLookupMixin, _IntrospectionEndpoint):
    CLIENT_AUTH_METHODS = ["client_secret_basic", "client_secret_post"]

    def check_permission(
        self, token: OAuth2Token, client: OAuth2Client, request: StarletteOAuth2Request
    ) -> bool:
        return token.check_client(client)  # pyright: ignore

    def introspect_token(self, token: OAuth2Token) -> dict[str, typing.Any]:
        return token.get_introspection_data(ISSUER)


# ---------------------------------------------------------------------------
# RFC 7591 -- Dynamic Client Registration
# ---------------------------------------------------------------------------


class ClientRegistrationEndpoint(_ClientRegistrationEndpoint):
    server: "AuthorizationServer"

    def authenticate_token(self, request: StarletteJsonRequest) -> User | str:
        return request.user if request.user is not None else "dynamic_client"

    def generate_client_id(self, request: StarletteJsonRequest) -> str:
        return generate_token(prefix=CLIENT_ID_PREFIX)

    def generate_client_secret(self, request: StarletteJsonRequest) -> str:
        return generate_token(prefix=CLIENT_SECRET_PREFIX)

    def generate_client_registration_info(
        self, client: OAuth2Client, request: StarletteJsonRequest
    ) -> dict[str, str]:
        assert client.registration_access_token is not None
        return {
            "registration_client_uri": str(
                request.url_for("oauth2:get_client", client_id=client.client_id)
            ),
            "registration_access_token": client.registration_access_token,
        }

    def save_client(
        self,
        client_info: dict[str, typing.Any],
        client_metadata: dict[str, typing.Any],
        request: StarletteJsonRequest,
    ) -> OAuth2Client:
        new_client = OAuth2Client(**client_info)
        new_client.set_client_metadata(client_metadata)
        if request.user is not None:
            new_client.user_id = request.user.id
        new_client.registration_access_token = generate_token(
            prefix=CLIENT_REGISTRATION_TOKEN_PREFIX
        )
        self.server.session.add(new_client)
        self.server.session.flush()
        return new_client

    def create_registration_response(
        self, request: StarletteJsonRequest
    ) -> tuple[int, dict[str, typing.Any], list[tuple[str, str]]]:
        """Build registration response, omitting secrets for public clients."""
        status, body, headers = super().create_registration_response(request)
        if isinstance(body, dict):
            _strip_public_client_secrets(body)
        return status, body, headers

    def get_server_metadata(self) -> dict[str, typing.Any]:
        return _build_metadata_dict(self.server)


# ---------------------------------------------------------------------------
# RFC 7592 -- Client Configuration (read / update / delete)
# ---------------------------------------------------------------------------


class ClientConfigurationEndpoint(_ClientConfigurationEndpoint):
    server: "AuthorizationServer"

    def generate_client_registration_info(
        self, client: OAuth2Client, request: StarletteJsonRequest
    ) -> dict[str, str]:
        return {
            "registration_client_uri": str(
                request.url_for("oauth2:get_client", client_id=client.client_id)
            ),
            "registration_access_token": client.registration_access_token,
        }

    def authenticate_token(self, request: StarletteJsonRequest) -> User | str | None:
        if request.user is not None:
            return request.user
        auth_header = request.headers.get("Authorization")
        if auth_header is None:
            return None
        scheme, _, bearer_value = auth_header.partition(" ")
        if scheme.lower() == "bearer" and bearer_value:
            return bearer_value
        return None

    def authenticate_client(self, request: StarletteJsonRequest) -> OAuth2Client | None:
        target_id = request.path_params.get("client_id")
        if target_id is None:
            return None
        stmt = select(OAuth2Client).where(
            OAuth2Client.deleted_at.is_(None),
            OAuth2Client.client_id == target_id,
        )
        client = self.server.session.execute(stmt).unique().scalar_one_or_none()
        if client is None:
            return None
        # Verify credential matches
        cred = request.credential
        if cred is None:
            return None
        if isinstance(cred, str):
            if not secrets.compare_digest(client.registration_access_token, cred):
                return None
        elif isinstance(cred, User):
            if client.user_id != cred.id:
                return None
        return client

    def create_read_client_response(
        self, client: OAuth2Client, request: StarletteJsonRequest
    ) -> tuple[int, dict[str, typing.Any], list[tuple[str, str]]]:
        """Build read response, omitting secrets for public clients."""
        status, body, headers = super().create_read_client_response(client, request)
        if isinstance(body, dict):
            _strip_public_client_secrets(body)
        return status, body, headers

    def check_permission(
        self, client: OAuth2Client, request: StarletteJsonRequest
    ) -> bool:
        return True

    def revoke_access_token(
        self, token: typing.Any, request: StarletteJsonRequest
    ) -> None:
        return None

    def delete_client(
        self, client: OAuth2Client, request: StarletteJsonRequest
    ) -> None:
        client.set_deleted_at()
        self.server.session.flush()

    def update_client(
        self,
        client: OAuth2Client,
        client_metadata: dict[str, typing.Any],
        request: StarletteJsonRequest,
    ) -> OAuth2Client:
        merged = {**client.client_metadata, **client_metadata}
        client.set_client_metadata(merged)
        self.server.session.add(client)
        self.server.session.flush()
        return client

    def get_server_metadata(self) -> dict[str, typing.Any]:
        return _build_metadata_dict(self.server)


# ---------------------------------------------------------------------------
# Core Authorization Server
# ---------------------------------------------------------------------------


class AuthorizationServer(_AuthorizationServer):
    if typing.TYPE_CHECKING:

        def create_endpoint_response(
            self, name: str, request: Request | None = None
        ) -> Response: ...

    def __init__(
        self,
        session: Session,
        *,
        error_uris: list[tuple[str, str]] | None = None,
    ) -> None:
        super().__init__(scopes_supported=[s.value for s in Scope])
        self.session = session
        self._error_uri_map = dict(error_uris) if error_uris else None
        self.register_token_generator("default", self._make_bearer_generator())

    # -- Factory --

    @classmethod
    def build(
        cls,
        session: Session,
        *,
        error_uris: list[tuple[str, str]] | None = None,
    ) -> typing.Self:
        server = cls(session, error_uris=error_uris)
        for ep_cls in (
            RevocationEndpoint,
            IntrospectionEndpoint,
            ClientRegistrationEndpoint,
            ClientConfigurationEndpoint,
        ):
            server.register_endpoint(ep_cls)
        register_grants(server)
        return server

    # -- Client persistence --

    def query_client(self, client_id: str) -> OAuth2Client | None:
        stmt = select(OAuth2Client).where(
            OAuth2Client.deleted_at.is_(None),
            OAuth2Client.client_id == client_id,
        )
        return self.session.execute(stmt).unique().scalar_one_or_none()

    # -- Token persistence --

    def save_token(
        self, token: dict[str, typing.Any], request: StarletteOAuth2Request
    ) -> None:
        raw_access = token.get("access_token")
        raw_refresh = token.get("refresh_token")
        hashed_token = {
            **token,
            "access_token": (
                get_token_hash(raw_access, secret=settings.SECRET)
                if raw_access is not None
                else None
            ),
            "refresh_token": (
                get_token_hash(raw_refresh, secret=settings.SECRET)
                if raw_refresh is not None
                else None
            ),
        }
        sub_type, sub = typing.cast(SubTypeValue, request.user)
        client = typing.cast(OAuth2Client, request.client)
        record = OAuth2Token(
            **hashed_token, client_id=client.client_id, sub_type=sub_type
        )
        record.sub = sub
        self.session.add(record)
        self.session.flush()

    # -- Request / response adapters --

    def create_oauth2_request(self, request: Request) -> StarletteOAuth2Request:
        return StarletteOAuth2Request(request)

    def create_json_request(self, request: Request) -> StarletteJsonRequest:
        return StarletteJsonRequest(request)

    def get_error_uri(self, request: Request, error: OAuth2Error) -> str | None:
        if self._error_uri_map is None or error.error is None:
            return None
        return self._error_uri_map.get(error.error)

    def send_signal(
        self, name: str, *args: tuple[typing.Any], **kwargs: dict[str, typing.Any]
    ) -> None:
        _log.debug(f"Authlib signal: {name}", *args, **kwargs)

    def handle_response(
        self,
        status_code: int,
        payload: dict[str, typing.Any] | str,
        headers: list[tuple[str, str]],
    ) -> Response:
        body = json.dumps(payload) if isinstance(payload, dict) else payload
        return Response(body, status_code, dict(headers))

    # -- Token generator --

    def _make_bearer_generator(self) -> BearerTokenGenerator:
        def _gen_access(
            client: OAuth2Client, grant_type: str, user: SubTypeValue, scope: str
        ) -> str:
            kind, _ = user
            return generate_token(prefix=ACCESS_TOKEN_PREFIX[kind])

        def _gen_refresh(
            client: OAuth2Client, grant_type: str, user: SubTypeValue, scope: str
        ) -> str:
            kind, _ = user
            return generate_token(prefix=REFRESH_TOKEN_PREFIX[kind])

        return BearerTokenGenerator(_gen_access, _gen_refresh)

    # Kept for backward compat -- callers may reference the old name
    create_bearer_token_generator = _make_bearer_generator

    # -- Authorization flow --

    def create_authorization_response(
        self,
        request: Request,
        grant_user: User | None = None,
        save_consent: bool = False,
    ) -> typing.Any:
        oauth2_req = (
            request
            if isinstance(request, StarletteOAuth2Request)
            else self.create_oauth2_request(request)
        )

        try:
            grant: AuthorizationCodeGrant = self.get_authorization_grant(oauth2_req)
        except UnsupportedResponseTypeError as exc:
            return self.handle_error_response(oauth2_req, exc)

        try:
            redirect = grant.validate_authorization_request()
            status, body, hdrs = grant.create_authorization_response(
                redirect, grant_user
            )
        except OAuth2Error as exc:
            return self.handle_error_response(oauth2_req, exc)

        if save_consent:
            self._persist_consent(oauth2_req, grant)

        return self.handle_response(status, body, hdrs)

    def _persist_consent(
        self, request: StarletteOAuth2Request, grant: AuthorizationCodeGrant
    ) -> None:
        assert grant.sub_type is not None
        assert grant.sub is not None
        assert grant.client is not None
        payload = request.payload
        assert payload is not None
        oauth2_grant_service.create_or_update_grant(
            self.session,
            sub_type=grant.sub_type,
            sub_id=grant.sub.id,
            client_id=grant.client.client_id,
            scope=payload.scope,
        )

    # -- Metadata introspection properties --

    @property
    def response_types_supported(self) -> list[str]:
        types: list[str] = []
        for grant_cls, _ in self._authorization_grants:
            rt = getattr(grant_cls, "RESPONSE_TYPES", None)
            if rt is not None:
                types.extend(rt)
        return types

    @property
    def response_modes_supported(self) -> list[str]:
        return ["query"]

    @property
    def grant_types_supported(self) -> list[str]:
        collected: set[str] = set()
        all_grants = [*self._authorization_grants, *self._token_grants]
        for grant_cls, _ in all_grants:
            gt = getattr(grant_cls, "GRANT_TYPE", None)
            if gt is not None:
                collected.add(gt)
        return list(collected)

    @property
    def token_endpoint_auth_methods_supported(self) -> list[str]:
        return ["client_secret_basic", "client_secret_post", "none"]

    @property
    def revocation_endpoint_auth_methods_supported(self) -> list[str]:
        return self._collect_endpoint_auth_methods(RevocationEndpoint.ENDPOINT_NAME)

    @property
    def introspection_endpoint_auth_methods_supported(self) -> list[str]:
        return self._collect_endpoint_auth_methods(IntrospectionEndpoint.ENDPOINT_NAME)

    def _collect_endpoint_auth_methods(self, endpoint_name: str) -> list[str]:
        methods: set[str] = set()
        for ep in self._endpoints.get(endpoint_name, []):
            methods.update(getattr(ep, "CLIENT_AUTH_METHODS", []))
        return list(methods)

    @property
    def code_challenge_methods_supported(self) -> list[str]:
        methods: set[str] = set()
        for _, exts in self._authorization_grants:
            for ext in exts:
                if isinstance(ext, CodeChallenge):
                    methods.update(ext.SUPPORTED_CODE_CHALLENGE_METHOD)
        return list(methods)
