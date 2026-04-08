"""Bearer token error responses with RFC 6750 WWW-Authenticate headers.

Provides two error classes used throughout the OAuth2 stack:

- ``InvalidTokenError`` -- generic invalid/expired token (HTTP 401)
- ``InsufficientScopeError`` -- caller lacks required scope (HTTP 403)

Both automatically populate the ``realm`` field from application settings
so that every WWW-Authenticate header stays consistent.
"""

from typing import Any

from authlib.oauth2.rfc6750 import InvalidTokenError as _BaseInvalidToken

from rapidly.config import settings

_REALM = settings.WWW_AUTHENTICATE_REALM


class InvalidTokenError(_BaseInvalidToken):
    """The access token is missing, expired, revoked, or otherwise invalid."""

    def __init__(self, description: str | None = None, **extra_attributes: Any) -> None:
        super().__init__(description, realm=_REALM, **extra_attributes)


class InsufficientScopeError(_BaseInvalidToken):
    """The access token's scope is too narrow for the requested resource.

    Returns HTTP 403 instead of the usual 401 to distinguish "valid
    credentials but wrong permissions" from "bad credentials".

    We subclass ``_BaseInvalidToken`` directly (rather than Authlib's
    ``InsufficientScopeError``) because the upstream class is missing the
    ``headers``-building logic that ``_BaseInvalidToken`` provides.

    See RFC 6750 section 3.1 for the specification.
    """

    error = "insufficient_scope"
    status_code = 403
    description = (
        "The request requires higher privileges than provided by the access token."
    )

    def __init__(self, required_scopes: set[str]) -> None:
        joined = " ".join(sorted(required_scopes))
        super().__init__(realm=_REALM, scope=joined)


__all__ = ["InsufficientScopeError", "InvalidTokenError"]
