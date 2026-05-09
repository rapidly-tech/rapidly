"""Tests for ``rapidly/integrations/discord/webhook.py``.

``get_branded_discord_embed`` decorates every outgoing Discord
webhook embed with Rapidly branding (colour / author / thumbnail /
footer). The merge order is load-bearing: the helper spreads
``_BRAND_DEFAULTS`` FIRST and the caller's embed SECOND so callers
can override any default when the event warrants it (e.g. a RED
error embed overriding the default Rapidly emerald). A regression
that reversed the spread would pin every embed to the defaults and
silently drop caller-provided titles / descriptions / fields.
"""

from __future__ import annotations

from rapidly.integrations.discord.webhook import (
    _BRAND_DEFAULTS,
    DiscordEmbed,
    get_branded_discord_embed,
)


class TestBrandDefaults:
    def test_color_is_rapidly_emerald(self) -> None:
        # ``25343`` = 0x62FF = Rapidly's primary emerald packed-RGB.
        # Pinning prevents a refresh that forgot to update both the
        # design system and the Discord embed renderer.
        assert _BRAND_DEFAULTS["color"] == 25343

    def test_author_name_is_rapidly(self) -> None:
        assert _BRAND_DEFAULTS["author"]["name"] == "Rapidly"

    def test_footer_text_is_branded(self) -> None:
        assert _BRAND_DEFAULTS["footer"]["text"] == "Powered by Rapidly"


class TestGetBrandedDiscordEmbed:
    def test_caller_empty_embed_gets_defaults(self) -> None:
        result = get_branded_discord_embed({})
        assert result["color"] == _BRAND_DEFAULTS["color"]
        assert result["author"] == _BRAND_DEFAULTS["author"]
        assert result["footer"] == _BRAND_DEFAULTS["footer"]
        assert result["thumbnail"] == _BRAND_DEFAULTS["thumbnail"]

    def test_caller_keys_override_defaults(self) -> None:
        # Load-bearing pin: caller-supplied fields WIN. A regression
        # that flipped the spread order (``{**caller, **defaults}``)
        # would pin every embed to the defaults and drop titles /
        # descriptions.
        override: DiscordEmbed = {"color": 0xFF0000, "title": "ALERT"}
        result = get_branded_discord_embed(override)
        assert result["color"] == 0xFF0000
        assert result["title"] == "ALERT"

    def test_caller_adds_new_fields_alongside_defaults(self) -> None:
        # New caller-only fields are added without disturbing
        # defaults.
        result = get_branded_discord_embed(
            {"description": "New file shared", "fields": [{"name": "k", "value": "v"}]}
        )
        assert result["description"] == "New file shared"
        assert result["fields"] == [{"name": "k", "value": "v"}]
        # Defaults still applied.
        assert result["color"] == _BRAND_DEFAULTS["color"]
        assert result["author"] == _BRAND_DEFAULTS["author"]

    def test_override_author_replaces_default(self) -> None:
        # Pin that caller-supplied ``author`` fully replaces the
        # default (dict-level override, not recursive merge) — this
        # matches the TypedDict spread semantics.
        result = get_branded_discord_embed({"author": {"name": "Customer Portal"}})
        assert result["author"] == {"name": "Customer Portal"}

    def test_helper_does_not_mutate_defaults(self) -> None:
        # ``{**_BRAND_DEFAULTS, **embed}`` creates a new dict; a
        # regression that did ``_BRAND_DEFAULTS.update(embed)``
        # would poison subsequent calls with the previous caller's
        # values.
        before_color = _BRAND_DEFAULTS["color"]
        get_branded_discord_embed({"color": 0xFF0000, "title": "ALERT"})
        assert _BRAND_DEFAULTS["color"] == before_color
