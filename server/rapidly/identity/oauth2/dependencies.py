"""FastAPI dependencies for the OAuth2 subsystem.

``get_authorization_server``
    Yields a sync-session-backed ``AuthorizationServer``. The session is
    committed on success and rolled back on error so that Authlib's
    synchronous grant handlers integrate cleanly with the async request
    lifecycle.

``get_token``
    Extracts and validates a bearer access token from the Authorization
    header, returning the corresponding ``OAuth2Token`` row.
"""

from collections.abc import Generator

from fastapi import Depends, Request
from fastapi.security import OpenIdConnect
from fastapi.security.utils import get_authorization_scheme_param

from rapidly.core.db.postgres import SyncSessionMaker
from rapidly.errors import Unauthorized
from rapidly.models import OAuth2Token
from rapidly.postgres import AsyncSession, get_db_session

from .actions.oauth2_token import oauth2_token as oauth2_token_service
from .authorization_server import AuthorizationServer
from .exceptions import InvalidTokenError

# Security scheme used by FastAPI's OpenAPI generator to document bearer auth
openid_scheme = OpenIdConnect(
    scheme_name="oidc",
    openIdConnectUrl="/.well-known/openid-configuration",
    auto_error=False,
)


# ---------------------------------------------------------------------------
# Token extraction
# ---------------------------------------------------------------------------


async def get_optional_token(
    authorization: str = Depends(openid_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> tuple[OAuth2Token | None, bool]:
    """Parse the Authorization header and look up the access token.

    Returns a ``(token_or_none, header_was_present)`` tuple so that
    downstream code can distinguish "no header" from "invalid token".
    """
    scheme, raw_token = get_authorization_scheme_param(authorization)
    if not authorization or scheme.lower() != "bearer":
        return None, False
    resolved = await oauth2_token_service.get_by_access_token(session, raw_token)
    return resolved, True


async def get_token(
    credentials: tuple[OAuth2Token | None, bool] = Depends(get_optional_token),
) -> OAuth2Token:
    """Require a valid bearer token or raise the appropriate HTTP error."""
    token_record, had_header = credentials
    if token_record is None:
        raise InvalidTokenError() if had_header else Unauthorized()
    return token_record


# ---------------------------------------------------------------------------
# Authorization server lifecycle
# ---------------------------------------------------------------------------


def get_authorization_server(
    request: Request,
) -> Generator[AuthorizationServer, None, None]:
    """Create a sync-session-scoped ``AuthorizationServer`` for one request.

    Commits the session on success, rolls back on any exception.
    """
    maker: SyncSessionMaker = request.state.sync_sessionmaker
    with maker() as sync_session:
        server = AuthorizationServer.build(sync_session)
        try:
            yield server
        except Exception:
            sync_session.rollback()
            raise
        else:
            sync_session.commit()
