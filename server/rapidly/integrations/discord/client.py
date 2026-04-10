"""Discord REST API client for bot operations.

Wraps the Discord v10 REST API to manage guild roles, member lookups,
and role assignments used by the Discord integration module.
"""

from typing import Any, Literal

import httpx
import structlog

from rapidly.config import settings

_log = structlog.get_logger()

BASE_URL = "https://discord.com/api/v10"


class DiscordClient:
    def __init__(self, scheme: Literal["Bot", "Bearer"], token: str) -> None:
        self.client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"Authorization": f"{scheme} {token}"},
            proxy=settings.DISCORD_PROXY_URL or None,
        )

    # ------------------------------------------------------------------
    # User
    # ------------------------------------------------------------------

    async def get_me(self) -> dict[str, Any]:
        resp = await self.client.get("/users/@me")
        self._raise_on_error(resp)
        return resp.json()

    # ------------------------------------------------------------------
    # Guild
    # ------------------------------------------------------------------

    async def get_guild(self, id: str) -> dict[str, Any]:
        resp = await self.client.get(f"/guilds/{id}")
        self._raise_on_error(resp)
        return resp.json()

    # ------------------------------------------------------------------
    # Member management
    # ------------------------------------------------------------------

    async def add_member(
        self,
        guild_id: str,
        discord_user_id: str,
        discord_user_access_token: str,
        role_id: str,
        nick: str | None = None,
    ) -> None:
        endpoint = f"/guilds/{guild_id}/members/{discord_user_id}"

        payload: dict[str, Any] = {
            "access_token": discord_user_access_token,
            "roles": [role_id],
        }
        if nick:
            payload["nick"] = nick

        resp = await self.client.put(endpoint, json=payload)
        self._raise_on_error(resp)

        if resp.status_code == 201:
            _log.info(
                "discord.add_member.success",
                guild_id=guild_id,
                discord_user_id=discord_user_id,
            )
            return

        # Member already present -- just ensure the role is assigned
        _log.debug(
            "discord.add_member.already_present",
            guild_id=guild_id,
            discord_user_id=discord_user_id,
        )
        await self.add_member_role(
            guild_id=guild_id,
            discord_user_id=discord_user_id,
            role_id=role_id,
        )

    async def add_member_role(
        self,
        guild_id: str,
        discord_user_id: str,
        role_id: str,
    ) -> None:
        endpoint = f"/guilds/{guild_id}/members/{discord_user_id}/roles/{role_id}"
        resp = await self.client.put(endpoint)
        self._raise_on_error(resp)

        _log.info(
            "discord.add_member_role.success",
            guild_id=guild_id,
            discord_user_id=discord_user_id,
            role_id=role_id,
        )
        return None

    async def remove_member_role(
        self,
        guild_id: str,
        discord_user_id: str,
        role_id: str,
    ) -> None:
        endpoint = f"/guilds/{guild_id}/members/{discord_user_id}/roles/{role_id}"
        resp = await self.client.delete(endpoint)
        self._raise_on_error(resp)

        _log.info(
            "discord.remove_member_role.success",
            guild_id=guild_id,
            discord_user_id=discord_user_id,
            role_id=role_id,
        )
        return None

    async def remove_member(self, guild_id: str, discord_user_id: str) -> None:
        endpoint = f"/guilds/{guild_id}/members/{discord_user_id}"
        resp = await self.client.delete(endpoint)
        self._raise_on_error(resp)

        _log.info(
            "discord.remove_member.success",
            guild_id=guild_id,
            discord_user_id=discord_user_id,
        )
        return None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _raise_on_error(self, response: httpx.Response) -> httpx.Response:
        response.raise_for_status()
        return response


bot_client = DiscordClient("Bot", settings.DISCORD_BOT_TOKEN)

__all__ = ["DiscordClient", "bot_client"]
