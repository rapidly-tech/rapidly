"""Signaling auth validators for ``session_kind="screen"``.

Registered at import time via the ``register_auth_validator`` decorator
from ``signaling.py``. Two validators:

- ``("screen", "host")`` — channel-secret HMAC check, identical in shape
  to the file-sharing host validator.
- ``("screen", "guest")`` — invite-token check (SISMEMBER on the
  ``file-sharing:screen:invite:{slug}`` SET).

This module is imported from ``rapidly.app`` (or any other bootstrap)
after ``signaling`` so the registry is populated before any WebSocket
connection can arrive.
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


@register_auth_validator("screen", "host")
async def _validate_screen_host(ctx: AuthContext) -> bool:
    """Screen host authenticates with the channel secret (HMAC compare).

    Same path and error shape as ``_validate_file_host``; intentionally
    kept as a separate registered function so the two chambers can
    diverge in the future without disturbing each other.
    """
    secret = ctx.msg.get("secret", "")
    if not secret or not hmac.compare_digest(ctx.channel.secret, _hash_secret(secret)):
        await _send_error(ctx.ws, "Authentication failed")
        await ctx.ws.close(code=4003, reason="Forbidden")
        return False
    return True


@register_auth_validator("screen", "guest")
async def _validate_screen_guest(ctx: AuthContext) -> bool:
    """Screen guest authenticates with an invite token.

    The invite was minted out-of-band by the host via
    ``POST /api/v1/screen/session/{slug}/invite`` and shared with the
    guest through the host's preferred channel (chat, email, link). The
    token is stored hashed in a Redis SET so ``SISMEMBER`` is the
    entire check.
    """
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
