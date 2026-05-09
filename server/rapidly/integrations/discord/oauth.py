"""Discord OAuth2 client factories.

Creates ``DiscordOAuth2`` instances for both user-facing login and
bot-installation flows.  HTTP traffic is routed through the optional
proxy when ``DISCORD_PROXY_URL`` is configured.
"""

import httpx
from httpx_oauth.clients.discord import DiscordOAuth2

from rapidly.config import settings

# Scopes required for each flow.
_USER_SCOPES = ["identify", "email", "guilds.join"]
_BOT_SCOPES = ["bot"]


class _ProxiedDiscordOAuth2(DiscordOAuth2):
    """DiscordOAuth2 subclass that honours the Rapidly proxy setting."""

    def get_httpx_client(self) -> httpx.AsyncClient:
        proxy_url = settings.DISCORD_PROXY_URL or None
        return httpx.AsyncClient(proxy=proxy_url)


def _build_client(scopes: list[str]) -> _ProxiedDiscordOAuth2:
    return _ProxiedDiscordOAuth2(
        settings.DISCORD_CLIENT_ID,
        settings.DISCORD_CLIENT_SECRET,
        scopes=scopes,
    )


user_client = _build_client(_USER_SCOPES)
bot_client = _build_client(_BOT_SCOPES)
