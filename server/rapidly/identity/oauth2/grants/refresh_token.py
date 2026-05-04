"""Refresh Token grant (RFC 6749 section 6).

Validates an existing refresh token, issues a fresh access+refresh pair,
and immediately revokes the old refresh token (rotation strategy).
"""

import time
import typing

from authlib.oauth2.rfc6749.grants import RefreshTokenGrant as _RefreshTokenGrant
from sqlalchemy import select

from rapidly.config import settings
from rapidly.core.crypto import get_token_hash
from rapidly.models import OAuth2Token

from ..sub_type import SubTypeValue

if typing.TYPE_CHECKING:
    from ..authorization_server import AuthorizationServer


class RefreshTokenGrant(_RefreshTokenGrant):
    """Refresh-token exchange with automatic rotation.

    After a successful token exchange the old refresh token is
    immediately revoked, and a brand-new refresh token is included in the
    response (see ``INCLUDE_NEW_REFRESH_TOKEN``).
    """

    server: "AuthorizationServer"
    INCLUDE_NEW_REFRESH_TOKEN = True
    TOKEN_ENDPOINT_AUTH_METHODS = ["client_secret_basic", "client_secret_post", "none"]

    def authenticate_refresh_token(self, refresh_token: str) -> OAuth2Token | None:
        hashed = get_token_hash(refresh_token, secret=settings.SECRET)
        stmt = select(OAuth2Token).where(OAuth2Token.refresh_token == hashed)
        record = self.server.session.execute(stmt).unique().scalar_one_or_none()
        if record is not None and not typing.cast(bool, record.is_revoked()):
            return record
        return None

    def authenticate_user(self, refresh_token: OAuth2Token) -> SubTypeValue | None:
        return refresh_token.get_sub_type_value()

    def revoke_old_credential(self, refresh_token: OAuth2Token) -> None:
        refresh_token.refresh_token_revoked_at = int(time.time())  # pyright: ignore
        self.server.session.add(refresh_token)
        self.server.session.flush()
