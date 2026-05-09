"""Authorization Code grant with PKCE and OpenID Connect extensions.

Integrates Authlib's ``AuthorizationCodeGrant`` with Rapidly's user /
workspace model, consent tracking, hashed code storage, and custom
token prefixes.  PKCE (RFC 7636) is always registered via ``CodeChallenge``.
"""

import typing
import uuid

from authlib.oauth2.rfc6749.errors import (
    AccessDeniedError,
    InvalidRequestError,
    OAuth2Error,
)
from authlib.oauth2.rfc6749.grants import (
    AuthorizationCodeGrant as _AuthorizationCodeGrant,
)
from authlib.oauth2.rfc6749.requests import OAuth2Request
from authlib.oauth2.rfc7636 import CodeChallenge as _CodeChallenge
from authlib.oidc.core.errors import ConsentRequiredError, LoginRequiredError
from authlib.oidc.core.grants import OpenIDCode as _OpenIDCode
from authlib.oidc.core.grants import OpenIDToken as _OpenIDToken
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from rapidly.config import settings
from rapidly.core.crypto import generate_token, get_token_hash
from rapidly.models import (
    OAuth2AuthorizationCode,
    OAuth2Client,
    User,
    Workspace,
    WorkspaceMembership,
)

from ..actions.oauth2_grant import oauth2_grant as oauth2_grant_service
from ..constants import AUTHORIZATION_CODE_PREFIX, JWT_CONFIG
from ..requests import StarletteOAuth2Request
from ..sub_type import SubType, SubTypeValue
from ..userinfo import UserInfo, generate_user_info

if typing.TYPE_CHECKING:
    from ..authorization_server import AuthorizationServer


# ---------------------------------------------------------------------------
# Nonce replay detection
# ---------------------------------------------------------------------------


def _nonce_already_used(
    session: Session, nonce: str, request: StarletteOAuth2Request
) -> bool:
    """Check whether an authorization code with this nonce already exists."""
    stmt = select(OAuth2AuthorizationCode).where(
        OAuth2AuthorizationCode.client_id == request.client_id,
        OAuth2AuthorizationCode.nonce == nonce,
    )
    return session.execute(stmt).unique().scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# Sub-type tracking mixin
# ---------------------------------------------------------------------------


class SubTypeGrantMixin:
    """Tracks which subject type (user / workspace) this grant targets."""

    sub_type: SubType | None = None
    sub: User | Workspace | None = None


# ---------------------------------------------------------------------------
# Authorization Code Grant
# ---------------------------------------------------------------------------


class AuthorizationCodeGrant(SubTypeGrantMixin, _AuthorizationCodeGrant):
    server: "AuthorizationServer"
    TOKEN_ENDPOINT_AUTH_METHODS = ["client_secret_basic", "client_secret_post", "none"]

    def __init__(self, request: OAuth2Request, server: "AuthorizationServer") -> None:
        super().__init__(request, server)
        self._hooks["before_create_authorization_response"] = set()
        self._hooks["before_validate_authorization_request_payload"] = {
            self._apply_default_scope
        }

    # -- Hooks --

    def _apply_default_scope(self, grant: "typing.Self", redirect_uri: str) -> None:
        """When the authorization request omits ``scope``, fall back to the client's default."""
        if self.request.payload.data.get("scope") is None:
            self.request.payload.data["scope"] = self.request.client.scope

    # Keep the old name so any external hook registrations still work.
    before_validate_authorization_request_payload = _apply_default_scope

    # -- Authorization response --

    def create_authorization_response(
        self, redirect_uri: str, grant_user: User | None
    ) -> tuple[int, str | dict[str, typing.Any], list[tuple[str, str]]]:
        payload = self.request.payload
        assert payload is not None
        if not grant_user:
            raise AccessDeniedError(state=payload.state, redirect_uri=redirect_uri)
        self.request.user = grant_user  # pyright: ignore
        self.execute_hook(
            "before_create_authorization_response", redirect_uri, grant_user
        )
        return super().create_authorization_response(redirect_uri, grant_user)  # pyright: ignore

    # -- Code lifecycle --

    def generate_authorization_code(self) -> str:
        return generate_token(prefix=AUTHORIZATION_CODE_PREFIX)

    def save_authorization_code(
        self, code: str, request: StarletteOAuth2Request
    ) -> OAuth2AuthorizationCode:
        payload = request.payload
        assert payload is not None
        assert self.sub_type is not None
        assert self.sub is not None

        auth_code = OAuth2AuthorizationCode(
            code=get_token_hash(code, secret=settings.SECRET),
            client_id=payload.client_id,
            sub_type=self.sub_type,
            scope=payload.scope,
            redirect_uri=payload.redirect_uri,
            nonce=payload.data.get("nonce"),
            code_challenge=payload.data.get("code_challenge"),
            code_challenge_method=payload.data.get("code_challenge_method"),
        )
        auth_code.sub = self.sub
        self.server.session.add(auth_code)
        self.server.session.flush()
        return auth_code

    def query_authorization_code(
        self, code: str, client: OAuth2Client
    ) -> OAuth2AuthorizationCode | None:
        hashed = get_token_hash(code, secret=settings.SECRET)
        stmt = select(OAuth2AuthorizationCode).where(
            OAuth2AuthorizationCode.code == hashed,
            OAuth2AuthorizationCode.client_id == client.client_id,
        )
        record = self.server.session.execute(stmt).unique().scalar_one_or_none()
        if record is not None and not typing.cast(bool, record.is_expired()):
            return record
        return None

    def delete_authorization_code(
        self, authorization_code: OAuth2AuthorizationCode
    ) -> None:
        self.server.session.delete(authorization_code)
        self.server.session.flush()

    def authenticate_user(
        self, authorization_code: OAuth2AuthorizationCode
    ) -> SubTypeValue | None:
        return authorization_code.get_sub_type_value()


# ---------------------------------------------------------------------------
# PKCE (RFC 7636)
# ---------------------------------------------------------------------------


class CodeChallenge(_CodeChallenge):
    """PKCE extension that requires ``code_challenge`` for public clients.

    Authlib's base ``CodeChallenge`` only enforces ``code_verifier`` at the
    token endpoint for public clients.  This subclass additionally requires
    ``code_challenge`` during the authorization request when the client's
    token-endpoint auth method is ``"none"`` (i.e. a public client), closing
    the gap where a public client could skip PKCE entirely.
    """

    def validate_code_challenge(
        self, grant: AuthorizationCodeGrant, redirect_uri: str
    ) -> None:
        request = grant.request
        challenge = request.payload.data.get("code_challenge")

        # Require PKCE for public clients (token_endpoint_auth_method == "none")
        if (
            self.required
            and not challenge
            and getattr(request, "client", None) is not None
            and request.client.token_endpoint_auth_method == "none"
        ):
            raise InvalidRequestError(
                "Public clients must use PKCE (missing 'code_challenge')"
            )

        # Delegate remaining validation (format checks, etc.) to the base class
        super().validate_code_challenge(grant, redirect_uri)


# ---------------------------------------------------------------------------
# OpenID Connect extensions
# ---------------------------------------------------------------------------


class OpenIDCode(_OpenIDCode):
    def __init__(self, session: Session, require_nonce: bool = False):
        super().__init__(require_nonce)
        self._db = session

    def exists_nonce(self, nonce: str, request: StarletteOAuth2Request) -> bool:
        return _nonce_already_used(self._db, nonce, request)

    def get_jwt_config(self, grant: AuthorizationCodeGrant) -> dict[str, typing.Any]:
        return JWT_CONFIG

    def generate_user_info(self, user: SubTypeValue, scope: str) -> UserInfo:
        return generate_user_info(user, scope)


class OpenIDToken(_OpenIDToken):
    def get_jwt_config(self, grant: AuthorizationCodeGrant) -> dict[str, typing.Any]:
        return JWT_CONFIG

    def generate_user_info(self, user: SubTypeValue, scope: str) -> UserInfo:
        return generate_user_info(user, scope)


# ---------------------------------------------------------------------------
# Sub + prompt validation (registered as grant extensions)
# ---------------------------------------------------------------------------


class InvalidSubError(OAuth2Error):
    """Raised when the ``sub`` parameter doesn't resolve to a valid entity."""

    error = "invalid_sub"


class ValidateSubAndPrompt:
    """Grant extension that validates ``sub_type``, ``sub``, and consent state.

    Registered as both a consent hook and a pre-authorization-response hook
    so that the subject is verified at each stage of the authorization flow.
    """

    def __init__(self, session: Session) -> None:
        self._db = session

    def __call__(self, grant: AuthorizationCodeGrant) -> None:
        grant.register_hook("after_validate_consent_request", self._on_consent)
        grant.register_hook(
            "before_create_authorization_response", self._on_pre_authz_response
        )

    # -- Hook handlers --

    def _on_consent(
        self,
        grant: AuthorizationCodeGrant,
        redirect_uri: str,
        redirect_fragment: bool = False,
    ) -> None:
        self._resolve_sub(grant, redirect_uri, redirect_fragment)
        self._check_consent(grant, redirect_uri, redirect_fragment)

    def _on_pre_authz_response(
        self,
        grant: AuthorizationCodeGrant,
        redirect_uri: str,
        redirect_fragment: bool = False,
    ) -> None:
        self._resolve_sub(grant, redirect_uri, redirect_fragment)
        if grant.sub is None:
            raise InvalidSubError()

    # -- Sub resolution --

    def _resolve_sub(
        self,
        grant: AuthorizationCodeGrant,
        redirect_uri: str,
        redirect_fragment: bool = False,
    ) -> None:
        payload = grant.request.payload
        assert payload is not None

        # Determine sub_type
        raw_sub_type: str | None = payload.data.get("sub_type")
        if raw_sub_type:
            try:
                grant.sub_type = SubType(raw_sub_type)
            except ValueError as exc:
                raise InvalidRequestError("Invalid sub_type") from exc
        else:
            client = typing.cast(OAuth2Client, grant.client)
            grant.sub_type = client.default_sub_type

        raw_sub: str | None = payload.data.get("sub")
        authenticated_user = grant.request.user

        if grant.sub_type == SubType.user:
            if raw_sub is not None:
                raise InvalidRequestError("Can't specify sub for user sub_type")
            grant.sub = authenticated_user
        elif (
            grant.sub_type == SubType.workspace
            and raw_sub is not None
            and authenticated_user is not None
        ):
            try:
                workspace_id = uuid.UUID(raw_sub)
            except ValueError as exc:
                raise InvalidSubError() from exc
            workspace = self._find_user_workspace(workspace_id, authenticated_user)
            if workspace is None:
                raise InvalidSubError()
            grant.sub = workspace

    # -- Consent checking --

    def _check_consent(
        self,
        grant: AuthorizationCodeGrant,
        redirect_uri: str,
        redirect_fragment: bool = False,
    ) -> None:
        client = grant.client
        assert client is not None

        # First-party clients bypass consent entirely
        if client.first_party and grant.sub_type is not None and grant.sub is not None:
            grant.prompt = "none"
            oauth2_grant_service.create_or_update_grant(
                self._db,
                sub_type=grant.sub_type,
                sub_id=grant.sub.id,
                client_id=grant.client.client_id,
                scope=client.scope,
            )
            return

        payload = grant.request.payload
        assert payload is not None
        prompt = payload.data.get("prompt")

        # Check existing consent
        scope_already_granted = False
        if grant.sub is not None:
            assert grant.client is not None
            assert grant.sub_type is not None
            scope_already_granted = oauth2_grant_service.has_granted_scope(
                self._db,
                sub_type=grant.sub_type,
                sub_id=grant.sub.id,
                client_id=grant.client.client_id,
                scope=payload.scope,
            )

        if prompt == "none":
            if grant.sub is None:
                raise LoginRequiredError(
                    redirect_uri=redirect_uri, redirect_fragment=redirect_fragment
                )
            if not scope_already_granted:
                raise ConsentRequiredError(
                    redirect_uri=redirect_uri, redirect_fragment=redirect_fragment
                )

        # Skip consent screen when scope was previously approved
        if prompt is None and scope_already_granted:
            grant.prompt = "none"

    # -- Database helpers --

    def _find_user_workspace(
        self, workspace_id: uuid.UUID, user: User
    ) -> Workspace | None:
        """Return the workspace only if the user is an active member."""
        stmt = (
            select(Workspace)
            .join(
                WorkspaceMembership,
                onclause=and_(
                    WorkspaceMembership.user_id == user.id,
                    WorkspaceMembership.deleted_at.is_(None),
                ),
            )
            .where(Workspace.id == workspace_id)
        )
        return self._db.execute(stmt).unique().scalar_one_or_none()
