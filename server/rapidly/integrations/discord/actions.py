"""Discord bot service: guild management and role synchronisation.

Provides helpers for listing guilds the bot has joined, syncing
share-access roles, and sending direct messages to Discord users.
"""

import structlog

from rapidly.config import settings
from rapidly.logging import Logger

from .client import bot_client
from .types import DiscordGuild, DiscordGuildRole

_log: Logger = structlog.get_logger()


async def get_guild(id: str) -> DiscordGuild:
    guild = await bot_client.get_guild(id)

    roles: list[DiscordGuildRole] = []
    for role in sorted(guild["roles"], key=lambda r: r["position"], reverse=True):
        # Keep standard roles
        if not role["managed"]:
            roles.append(
                DiscordGuildRole.model_validate({**role, "is_rapidly_bot": False})
            )
            continue

        # Keep only our bot role
        if tags := role.get("tags"):
            if tags.get("bot_id") == settings.DISCORD_CLIENT_ID:
                roles.append(
                    DiscordGuildRole.model_validate({**role, "is_rapidly_bot": True})
                )

    return DiscordGuild(name=guild["name"], roles=roles)


async def add_member(
    guild_id: str, role_id: str, account_id: str, access_token: str
) -> None:
    await bot_client.add_member(
        guild_id=guild_id,
        discord_user_id=account_id,
        discord_user_access_token=access_token,
        role_id=role_id,
    )


async def remove_member_role(guild_id: str, role_id: str, account_id: str) -> None:
    await bot_client.remove_member_role(
        guild_id=guild_id,
        discord_user_id=account_id,
        role_id=role_id,
    )


async def remove_member(guild_id: str, account_id: str) -> None:
    await bot_client.remove_member(guild_id=guild_id, discord_user_id=account_id)
