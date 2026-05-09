"""Discord OAuth endpoints and bot-guild management.

Handles the Discord OAuth2 bot installation flow, guild (server)
listing for bot configuration, and role-sync callbacks for
Discord-based access control.
"""

from typing import Any
from uuid import UUID

import structlog
from fastapi import Request
from fastapi.responses import RedirectResponse
from httpx_oauth.oauth2 import GetAccessTokenError

from rapidly.config import settings
from rapidly.core import jwt
from rapidly.core.http import ReturnTo, add_query_parameters, get_safe_return_url
from rapidly.errors import Unauthorized
from rapidly.identity.auth.dependencies import WebUserWrite
from rapidly.openapi import APITag
from rapidly.routing import APIRouter

from . import actions as discord_bot_service
from . import oauth
from .types import DiscordGuild

_log = structlog.get_logger()

router = APIRouter(
    prefix="/integrations/discord",
    tags=["integrations_discord", APITag.private],
)


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------


def get_decoded_token_state(state: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token=state,
            secret=settings.SECRET,
            type="discord_oauth",
        )
    except jwt.DecodeError as exc:
        raise Unauthorized("Invalid state") from exc


# ---------------------------------------------------------------------------
# Guild lookup
# ---------------------------------------------------------------------------


@router.get("/guild/lookup", response_model=DiscordGuild)
async def discord_guild_lookup(
    guild_token: str, auth_subject: WebUserWrite
) -> DiscordGuild:
    try:
        token_data = jwt.decode(
            token=guild_token,
            secret=settings.SECRET,
            type="discord_guild_token",
        )
        guild_id = token_data["guild_id"]
    except (KeyError, jwt.DecodeError, jwt.ExpiredSignatureError) as exc:
        raise Unauthorized() from exc

    return await discord_bot_service.get_guild(guild_id)


# ---------------------------------------------------------------------------
# Bot authorization
# ---------------------------------------------------------------------------


@router.get(
    "/bot/authorize",
    name="integrations.discord.bot_authorize",
)
async def discord_bot_authorize(
    return_to: ReturnTo, request: Request, auth_subject: WebUserWrite
) -> RedirectResponse:
    state = {
        "auth_type": "bot",
        "user_id": str(auth_subject.subject.id),
        "return_to": return_to,
    }

    encoded = jwt.encode(data=state, secret=settings.SECRET, type="discord_oauth")

    auth_url = await oauth.bot_client.get_authorization_url(
        redirect_uri=str(request.url_for("integrations.discord.bot_callback")),
        state=encoded,
        extras_params=dict(
            permissions=settings.DISCORD_BOT_PERMISSIONS,
        ),
    )
    return RedirectResponse(auth_url, 303)


@router.get("/bot/callback", name="integrations.discord.bot_callback")
async def discord_bot_callback(
    auth_subject: WebUserWrite,
    request: Request,
    state: str,
    code: str | None = None,
    code_verifier: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    decoded = get_decoded_token_state(state)
    return_to = decoded["return_to"]

    if code is None or error is not None:
        redirect = get_safe_return_url(
            add_query_parameters(
                return_to, error=error or "Failed to authorize Discord bot."
            )
        )
        return RedirectResponse(redirect, 303)

    try:
        access_token = await oauth.bot_client.get_access_token(
            code, str(request.url_for("integrations.discord.bot_callback"))
        )
    except GetAccessTokenError as exc:
        redirect = get_safe_return_url(
            add_query_parameters(
                return_to, error="Failed to get access token. Please try again later."
            )
        )
        _log.error("Failed to get Discord bot access token", error=str(exc))
        return RedirectResponse(redirect, 303)

    caller_id = UUID(decoded["user_id"])
    if caller_id != auth_subject.subject.id or decoded["auth_type"] != "bot":
        raise Unauthorized()

    guild_id = access_token["guild"]["id"]

    signed_guild = jwt.encode(
        data={"guild_id": guild_id},
        secret=settings.SECRET,
        type="discord_guild_token",
    )

    redirect = get_safe_return_url(
        add_query_parameters(return_to, guild_token=signed_guild, guild_id=guild_id)
    )

    return RedirectResponse(redirect, 303)
