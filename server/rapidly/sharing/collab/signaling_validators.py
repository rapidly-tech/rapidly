"""Signaling auth validators for ``session_kind="collab"``.

Same shape as the other chambers. Host = session creator (secret
holder). Guest = anyone who joined via an invite link.
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


@register_auth_validator("collab", "host")
async def _validate_collab_host(ctx: AuthContext) -> bool:
    """Collab host — channel secret HMAC check."""
    secret = ctx.msg.get("secret", "")
    if not secret or not hmac.compare_digest(ctx.channel.secret, _hash_secret(secret)):
        await _send_error(ctx.ws, "Authentication failed")
        await ctx.ws.close(code=4003, reason="Forbidden")
        return False
    return True


@register_auth_validator("collab", "guest")
async def _validate_collab_guest(ctx: AuthContext) -> bool:
    """Collab guest — invite-token SISMEMBER check."""
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
