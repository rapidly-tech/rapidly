"""Discord guild and role Pydantic models.

Provides ``DiscordGuild`` and ``DiscordGuildRole`` schemas used by the
Discord bot integration to represent guild structures and role assignments.
"""

from typing import Any

from pydantic import field_validator
from pydantic_extra_types.color import Color

from rapidly.core.types import Schema

# ---------------------------------------------------------------------------
# Role
# ---------------------------------------------------------------------------


class DiscordGuildRole(Schema):
    id: str
    name: str
    position: int
    is_rapidly_bot: bool
    color: Color

    @field_validator("color", mode="before")
    @classmethod
    def int_color_to_hex(cls, v: Any) -> str:
        if isinstance(v, int):
            return hex(v)[2:].zfill(6)
        return v


# ---------------------------------------------------------------------------
# Guild
# ---------------------------------------------------------------------------


class DiscordGuild(Schema):
    name: str
    roles: list[DiscordGuildRole]
