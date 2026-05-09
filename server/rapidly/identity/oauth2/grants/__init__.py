"""OAuth2 grant types: authorization code, refresh token, and web grants.

Registers all supported grant types with the authorization server
during application startup.
"""

import typing

from .authorization_code import (
    AuthorizationCodeGrant,
    CodeChallenge,
    OpenIDCode,
    OpenIDToken,
    ValidateSubAndPrompt,
)
from .refresh_token import RefreshTokenGrant
from .web import WebGrant

if typing.TYPE_CHECKING:
    from ..authorization_server import AuthorizationServer

# All grant classes that the server can issue tokens through.
_GRANT_CLASSES = (AuthorizationCodeGrant, RefreshTokenGrant, WebGrant)


def _build_auth_code_extensions(
    server: "AuthorizationServer",
) -> list[typing.Any]:
    """Return the extension stack for the authorization-code grant."""
    return [
        CodeChallenge(),
        OpenIDCode(server.session, require_nonce=False),
        OpenIDToken(),
        ValidateSubAndPrompt(server.session),
    ]


def register_grants(server: "AuthorizationServer") -> None:
    """Wire every supported grant type into *server*."""
    server.register_grant(
        AuthorizationCodeGrant,
        _build_auth_code_extensions(server),
    )
    server.register_grant(RefreshTokenGrant)
    server.register_grant(WebGrant)


__all__ = ["AuthorizationCodeGrant", "CodeChallenge", "register_grants"]
