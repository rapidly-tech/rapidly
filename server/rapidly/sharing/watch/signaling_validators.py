"""Signaling auth validators for ``session_kind="watch"``.

Registered at import time via the ``register_auth_validator`` decorator.
Same two-validator pattern as the Screen chamber: host proves the
channel secret, guest proves the invite token.
"""

from __future__ import annotations

import hmac

from rapidly.sharing.file_sharing.queries import _hash_secret
from rapidly.sharing.file_sharing.signaling import (
    AuthContext,
    _send_error,
    register_auth_validator,
)

from .actions import validate_invite_token


@register_auth_validator("watch", "host")
async def _validate_watch_host(ctx: AuthContext) -> bool:
    """Watch host — channel secret HMAC check."""
    secret = ctx.msg.get("secret", "")
    if not secret or not hmac.compare_digest(ctx.channel.secret, _hash_secret(secret)):
        await _send_error(ctx.ws, "Authentication failed")
        await ctx.ws.close(code=4003, reason="Forbidden")
        return False
    return True


@register_auth_validator("watch", "guest")
async def _validate_watch_guest(ctx: AuthContext) -> bool:
    """Watch guest — invite-token SISMEMBER check."""
    token = ctx.msg.get("token", "")
    if not token or not isinstance(token, str):
        await _send_error(ctx.ws, "Authentication failed")
        await ctx.ws.close(code=4003, reason="Forbidden")
        return False
    valid = await validate_invite_token(ctx.repo._redis, ctx.slug, token)
    if not valid:
        await _send_error(ctx.ws, "Authentication failed")
        await ctx.ws.close(code=4003, reason="Forbidden")
        return False
    return True
