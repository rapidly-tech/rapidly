"""ASGI middleware for pre-route credential resolution.

``AuthPrincipalMiddleware`` runs before any route handler.  It reads the
bearer token or session cookie, looks up the matching credential store,
and places the resulting ``AuthPrincipal`` on the ASGI scope so that
downstream FastAPI dependencies never need to repeat the lookup.
"""

import logfire
import structlog
from fastapi import Request
from fastapi.security.utils import get_authorization_scheme_param
from starlette.types import ASGIApp, Receive, Send
from starlette.types import Scope as ASGIScope

from rapidly.core.utils import now_utc
from rapidly.customers.customer_session.actions import (
    CUSTOMER_SESSION_TOKEN_PREFIX,
)
from rapidly.customers.customer_session.actions import (
    customer_session as customer_session_service,
)
from rapidly.identity.member_session.actions import (
    member_session as member_session_service,
)
from rapidly.identity.oauth2.actions.oauth2_token import (
    oauth2_token as oauth2_token_service,
)
from rapidly.identity.oauth2.constants import is_registration_token_prefix
from rapidly.identity.oauth2.exception_handlers import (
    OAuth2Error,
    oauth2_error_exception_handler,
)
from rapidly.identity.oauth2.exceptions import InvalidTokenError
from rapidly.logging import Logger
from rapidly.models import (
    CustomerSession,
    MemberSession,
    OAuth2Token,
    UserSession,
    WorkspaceAccessToken,
)
from rapidly.models.member_session import MEMBER_SESSION_TOKEN_PREFIX
from rapidly.platform.workspace_access_token import (
    actions as workspace_access_token_service,
)
from rapidly.postgres import AsyncSession
from rapidly.sentry import set_sentry_user
from rapidly.worker import dispatch_task

from . import actions as auth_service
from .models import Anonymous, AuthPrincipal, Subject
from .scope import Scope

_log: Logger = structlog.get_logger(__name__)

_ANONYMOUS: AuthPrincipal[Anonymous] = AuthPrincipal(Anonymous(), set(), None)

# Authorization header scheme we accept.
_BEARER_SCHEME: str = "bearer"


# ── Credential lookup helpers ──────────────────────────────────────────


async def get_user_session(
    request: Request, session: AsyncSession
) -> UserSession | None:
    """Look up the browser session cookie and return the matching ``UserSession``."""
    return await auth_service.authenticate(session, request)


def get_bearer_token(request: Request) -> str | None:
    """Parse the Authorization header and return the token value, or ``None`` if absent/invalid."""
    scheme, value = get_authorization_scheme_param(request.headers.get("Authorization"))
    if (
        not scheme
        or not value
        or scheme.lower() != _BEARER_SCHEME
        or not value.isascii()
    ):
        return None
    return value


async def get_oauth2_token(session: AsyncSession, value: str) -> OAuth2Token | None:
    """Fetch the ``OAuth2Token`` row matching the supplied access token string."""
    return await oauth2_token_service.get_by_access_token(session, value)


async def get_workspace_access_token(
    session: AsyncSession, value: str
) -> WorkspaceAccessToken | None:
    """Retrieve an OAT by raw token and schedule a background job to update its last-used time."""
    token = await workspace_access_token_service.get_by_token(session, value)

    if token is not None:
        dispatch_task(
            "workspace_access_token.record_usage",
            workspace_access_token_id=token.id,
            last_used_at=now_utc().timestamp(),
        )

    return token


async def get_customer_session(
    session: AsyncSession, value: str
) -> CustomerSession | None:
    """Resolve a customer portal session from its raw token."""
    return await customer_session_service.get_by_token(session, value)


async def get_member_session(session: AsyncSession, value: str) -> MemberSession | None:
    """Resolve a member portal session from its raw token."""
    return await member_session_service.get_by_token(session, value)


async def _resolve_from_token(
    session: AsyncSession, token: str
) -> AuthPrincipal[Subject]:
    """Try each credential store in turn until the token matches, or raise ``InvalidTokenError``."""
    if is_registration_token_prefix(token):
        return _ANONYMOUS

    # Tokens with a known prefix can only be one type — reject immediately on mismatch.
    if token.startswith(MEMBER_SESSION_TOKEN_PREFIX):
        ms = await get_member_session(session, token)
        if ms:
            return AuthPrincipal(ms.member, {Scope.customer_portal_write}, ms)
        raise InvalidTokenError()

    if token.startswith(CUSTOMER_SESSION_TOKEN_PREFIX):
        cs = await get_customer_session(session, token)
        if cs:
            return AuthPrincipal(cs.customer, {Scope.customer_portal_write}, cs)
        raise InvalidTokenError()

    # Unprefixed tokens: check OAT, then OAuth2.
    if oat := await get_workspace_access_token(session, token):
        return AuthPrincipal(oat.workspace, oat.scopes, oat)

    if o2t := await get_oauth2_token(session, token):
        return AuthPrincipal(o2t.sub, o2t.scopes, o2t)

    raise InvalidTokenError()


# ── Top-level resolver ─────────────────────────────────────────────────


async def get_auth_subject(
    request: Request, session: AsyncSession
) -> AuthPrincipal[Subject]:
    """Determine the caller identity from the bearer token or browser session cookie."""
    token = get_bearer_token(request)
    if token is not None:
        return await _resolve_from_token(session, token)

    user_session = await get_user_session(request, session)
    if user_session is not None:
        return AuthPrincipal(user_session.user, set(user_session.scopes), user_session)

    return _ANONYMOUS


# ── Path-based auth bypass ─────────────────────────────────────────────

# File-sharing endpoints authenticate via HKDF-derived reader tokens, not the standard Rapidly flow.
# Only paths explicitly listed in _FILE_SHARING_SELF_AUTH_PATHS bypass the auth middleware
# (auth_subject set to Anonymous). These endpoints handle their own authentication
# via channel secrets / reader tokens / payment tokens.
#
# DEFAULT-DENY: Any NEW endpoint added under /api/file-sharing/ will require standard
# Rapidly auth unless explicitly added to _FILE_SHARING_SELF_AUTH_PATHS below.
_FILE_SHARING_PREFIX: str = "/api/file-sharing/"
_FILE_SHARING_SELF_AUTH_PATHS: tuple[str, ...] = (
    "/api/file-sharing/signal/",  # WebSocket signaling (slug in path)
    "/api/file-sharing/channels/",  # Channel operations on specific channels (slug in path)
    "/api/file-sharing/ice/",  # ICE config (slug in path)
)


def _needs_auth(path: str) -> bool:
    """Return False for file-sharing routes that handle authentication independently.

    Default-deny: all /api/file-sharing/* paths require standard auth UNLESS
    they are explicitly listed in _FILE_SHARING_SELF_AUTH_PATHS. This prevents
    new endpoints from silently bypassing auth.

    Uses segment-aware matching: a prefix like ``/api/file-sharing/secret``
    matches ``/api/file-sharing/secret`` exactly **and**
    ``/api/file-sharing/secret/...`` (with a ``/`` separator), but NOT
    ``/api/file-sharing/secrets-admin``.
    """
    if not path.startswith(_FILE_SHARING_PREFIX):
        return True
    # Segment-aware prefix matching: the path must either equal the prefix
    # exactly, or continue with a '/' (preventing partial-segment collisions).
    for p in _FILE_SHARING_SELF_AUTH_PATHS:
        if path == p or path.startswith(p if p.endswith("/") else p + "/"):
            return False
    return True


# ── ASGI middleware ────────────────────────────────────────────────────


class AuthPrincipalMiddleware:
    """Populates the ASGI scope with an ``AuthPrincipal`` before the request reaches any route."""

    __slots__ = ("app",)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: ASGIScope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            # WebSocket and other non-HTTP scopes get an anonymous principal
            # by default.  File-sharing WebSockets handle their own auth via
            # the first signaling message; any *future* WS endpoint that
            # forgets to authenticate will safely default to anonymous rather
            # than silently running with no principal at all.
            if "state" in scope:
                scope["state"].setdefault("auth_subject", _ANONYMOUS)
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if not _needs_auth(path):
            scope["state"]["auth_subject"] = _ANONYMOUS
            await self.app(scope, receive, send)
            return

        session: AsyncSession = scope["state"]["async_session"]
        request = Request(scope)

        try:
            auth_subject = await get_auth_subject(request, session)
        except OAuth2Error as e:
            response = await oauth2_error_exception_handler(request, e)
            return await response(scope, receive, send)

        scope["state"]["auth_subject"] = auth_subject

        with logfire.set_baggage(**auth_subject.log_context):
            _log.info("Authenticated subject", **auth_subject.log_context)
            set_sentry_user(auth_subject)
            await self.app(scope, receive, send)
