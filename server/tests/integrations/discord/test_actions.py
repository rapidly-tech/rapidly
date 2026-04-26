"""Tests for ``rapidly/integrations/discord/actions.py``.

``get_guild`` is the single non-trivial action — it fetches a guild
from the Discord bot client and filters the role list with two
load-bearing rules:

1. **Managed roles are filtered out** — EXCEPT the Rapidly bot's
   own role (identified by ``tags.bot_id == settings.DISCORD_CLIENT_ID``).
   Dropping the exception would hide the role that workspace admins
   need to assign to paying customers. Keeping all managed roles
   would surface Discord integration roles (Stripe bot, etc) in
   the workspace picker where they don't belong.

2. **Roles sorted by ``position`` DESC** — matches the way Discord
   renders the role list, so admins see the highest-priority role
   at the top of the picker.

The thin ``add_member`` / ``remove_member_role`` / ``remove_member``
delegates don't carry logic worth pinning independently — a
regression there would surface as a test failure in end-to-end
guild-role tests.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from rapidly.integrations.discord.actions import get_guild


def _role(
    *,
    role_id: str,
    name: str,
    position: int,
    managed: bool,
    color: int = 0,
    bot_id: str | None = None,
) -> dict[str, Any]:
    role: dict[str, Any] = {
        "id": role_id,
        "name": name,
        "position": position,
        "managed": managed,
        "color": color,
    }
    if bot_id is not None:
        role["tags"] = {"bot_id": bot_id}
    return role


@pytest.mark.asyncio
class TestGetGuild:
    async def test_filters_managed_third_party_roles(self) -> None:
        # A Stripe bot's role (managed=True, tags.bot_id != ours)
        # must NOT reach the returned role list — workspace admins
        # should only see their own roles + Rapidly's bot role.
        guild_payload: dict[str, Any] = {
            "name": "Acme Community",
            "roles": [
                _role(role_id="1", name="@everyone", position=0, managed=False),
                _role(
                    role_id="2",
                    name="Stripe Bot",
                    position=10,
                    managed=True,
                    bot_id="stripe_bot_id",
                ),
            ],
        }
        with patch(
            "rapidly.integrations.discord.actions.bot_client.get_guild",
            new=AsyncMock(return_value=guild_payload),
        ):
            guild = await get_guild("guild123")
        names = [r.name for r in guild.roles]
        assert names == ["@everyone"]

    async def test_keeps_rapidly_bot_role(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Load-bearing exception: the Rapidly bot's OWN managed role
        # must survive the filter (identified by tags.bot_id ==
        # settings.DISCORD_CLIENT_ID). Dropping it would break the
        # "assign Rapidly bot role" admin flow.
        monkeypatch.setattr(
            "rapidly.integrations.discord.actions.settings.DISCORD_CLIENT_ID",
            "rapidly_bot_id",
        )
        guild_payload: dict[str, Any] = {
            "name": "Acme",
            "roles": [
                _role(
                    role_id="r1",
                    name="Rapidly",
                    position=5,
                    managed=True,
                    bot_id="rapidly_bot_id",
                ),
            ],
        }
        with patch(
            "rapidly.integrations.discord.actions.bot_client.get_guild",
            new=AsyncMock(return_value=guild_payload),
        ):
            guild = await get_guild("guild123")
        assert len(guild.roles) == 1
        assert guild.roles[0].is_rapidly_bot is True

    async def test_sorts_roles_by_position_descending(self) -> None:
        # Discord renders roles top-to-bottom by position DESC; the
        # admin UI mirrors that order so the highest-priority role
        # surfaces first in the picker.
        guild_payload: dict[str, Any] = {
            "name": "Acme",
            "roles": [
                _role(role_id="1", name="low", position=1, managed=False),
                _role(role_id="2", name="high", position=10, managed=False),
                _role(role_id="3", name="mid", position=5, managed=False),
            ],
        }
        with patch(
            "rapidly.integrations.discord.actions.bot_client.get_guild",
            new=AsyncMock(return_value=guild_payload),
        ):
            guild = await get_guild("guild123")
        names = [r.name for r in guild.roles]
        assert names == ["high", "mid", "low"]

    async def test_unmanaged_roles_are_is_rapidly_bot_false(self) -> None:
        guild_payload: dict[str, Any] = {
            "name": "Acme",
            "roles": [
                _role(role_id="1", name="admin", position=5, managed=False),
            ],
        }
        with patch(
            "rapidly.integrations.discord.actions.bot_client.get_guild",
            new=AsyncMock(return_value=guild_payload),
        ):
            guild = await get_guild("guild123")
        assert guild.roles[0].is_rapidly_bot is False

    async def test_managed_role_without_bot_tags_is_filtered(self) -> None:
        # A managed role without a ``tags`` dict (or with tags that
        # don't carry bot_id) is filtered out — matches Discord's
        # shape for admin-created "linked role" types.
        guild_payload: dict[str, Any] = {
            "name": "Acme",
            "roles": [
                _role(role_id="1", name="linked", position=5, managed=True),
            ],
        }
        with patch(
            "rapidly.integrations.discord.actions.bot_client.get_guild",
            new=AsyncMock(return_value=guild_payload),
        ):
            guild = await get_guild("guild123")
        assert guild.roles == []

    async def test_name_flows_through(self) -> None:
        guild_payload: dict[str, Any] = {"name": "Rapidly Community", "roles": []}
        with patch(
            "rapidly.integrations.discord.actions.bot_client.get_guild",
            new=AsyncMock(return_value=guild_payload),
        ):
            guild = await get_guild("guild123")
        assert guild.name == "Rapidly Community"
