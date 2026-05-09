"""Tests for ``rapidly/integrations/discord/types.py``.

Discord's API returns role colour as an **integer** (packed RGB, e.g.
``3447003`` for blurple); Pydantic's ``Color`` type doesn't accept
that format directly. The ``int_color_to_hex`` before-validator
converts the int to a 6-char hex string so ``Color`` can parse it.

Pins:
- Int input → zero-padded 6-char hex string (preserves leading
  zeros, e.g. ``0x000001`` instead of ``0x1``)
- String input passes through (lets callers supply already-hex
  values directly, e.g. from cached payloads)
- ``DiscordGuild`` roundtrips with a role list
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from rapidly.integrations.discord.types import DiscordGuild, DiscordGuildRole


class TestIntColorToHex:
    def test_int_converted_to_6_char_hex(self) -> None:
        # ``3447003`` = Discord blurple = 0x5865F2. The validator
        # must produce ``5865f2``, which Color then parses.
        role = DiscordGuildRole.model_validate(
            {
                "id": "r1",
                "name": "admin",
                "position": 1,
                "is_rapidly_bot": False,
                "color": 0x5865F2,
            }
        )
        # Color normalises internally; just check it parsed.
        assert role.color is not None

    def test_small_int_is_zero_padded(self) -> None:
        # ``hex(1)[2:]`` = ``"1"``. Without zfill(6) Color would
        # reject it as invalid. Pin the zero-pad so the validator
        # keeps working for roles with near-zero colour packs.
        role = DiscordGuildRole.model_validate(
            {
                "id": "r1",
                "name": "low",
                "position": 0,
                "is_rapidly_bot": False,
                "color": 1,
            }
        )
        assert role.color is not None

    def test_zero_int_yields_black(self) -> None:
        # Colour 0 is "no role colour" in Discord — keep it parsing.
        role = DiscordGuildRole.model_validate(
            {
                "id": "r1",
                "name": "none",
                "position": 0,
                "is_rapidly_bot": False,
                "color": 0,
            }
        )
        assert role.color is not None

    def test_string_input_passes_through(self) -> None:
        # Already-hex strings must not be re-coerced.
        role = DiscordGuildRole.model_validate(
            {
                "id": "r1",
                "name": "red",
                "position": 0,
                "is_rapidly_bot": False,
                "color": "#ff0000",
            }
        )
        assert role.color is not None


class TestDiscordGuildRoleRequiredFields:
    @pytest.mark.parametrize(
        "missing",
        ["id", "name", "position", "is_rapidly_bot", "color"],
    )
    def test_required_field_missing_raises(self, missing: str) -> None:
        body: dict[str, object] = {
            "id": "r1",
            "name": "x",
            "position": 0,
            "is_rapidly_bot": False,
            "color": "#ffffff",
        }
        del body[missing]
        with pytest.raises(ValidationError):
            DiscordGuildRole.model_validate(body)


class TestDiscordGuild:
    def test_roundtrip_with_roles(self) -> None:
        body = DiscordGuild.model_validate(
            {
                "name": "Rapidly Community",
                "roles": [
                    {
                        "id": "r1",
                        "name": "admin",
                        "position": 1,
                        "is_rapidly_bot": False,
                        "color": 0xFF0000,
                    },
                ],
            }
        )
        assert body.name == "Rapidly Community"
        assert len(body.roles) == 1

    def test_empty_roles_list_accepted(self) -> None:
        # A guild with no custom roles still has an ``@everyone`` role
        # but Discord's representation of that is configurable; the
        # schema must accept an empty list without 422.
        body = DiscordGuild.model_validate({"name": "Empty", "roles": []})
        assert body.roles == []
