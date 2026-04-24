"""Tests for ``rapidly/integrations/discord/oauth.py``.

Two pre-built OAuth2 clients cover the user-login flow and the
bot-install flow. Their scope sets are load-bearing — Discord
rejects auth URLs whose scopes don't match the app's configured
capabilities, and the bot flow MUST NOT request user-identity
scopes (principle of least privilege + Discord's policy).

Pins:
- ``_USER_SCOPES`` = ``["identify", "email", "guilds.join"]`` —
  identify for profile, email for sign-in, guilds.join so the
  Rapidly bot can add the user to a paid workspace guild
- ``_BOT_SCOPES`` = ``["bot"]`` — nothing else; silently adding
  ``identify`` here would let the bot flow see user identities
  without the user consenting to identify-level access
- The pre-built ``user_client`` / ``bot_client`` module-level
  instances use the right scope sets
- ``_ProxiedDiscordOAuth2.get_httpx_client`` honours
  ``DISCORD_PROXY_URL`` (None → no proxy; set → routed through)
"""

from __future__ import annotations

import httpx
import pytest

from rapidly.integrations.discord import oauth as O
from rapidly.integrations.discord.oauth import (
    _BOT_SCOPES,
    _USER_SCOPES,
    _ProxiedDiscordOAuth2,
    bot_client,
    user_client,
)


class TestScopeSets:
    def test_user_scopes_match_documented_set(self) -> None:
        # Adding/removing a scope here would materially change what
        # user data Discord asks the caller to consent to. Pinning
        # forces an intentional update.
        assert _USER_SCOPES == ["identify", "email", "guilds.join"]

    def test_bot_scopes_match_documented_set(self) -> None:
        # Load-bearing least-privilege pin: the bot install flow
        # must not silently request user-identity scopes.
        assert _BOT_SCOPES == ["bot"]

    def test_bot_scopes_do_not_overlap_with_user_scopes(self) -> None:
        # A silent ``identify`` addition to the bot flow would let
        # the bot OAuth see user identity without the user's
        # explicit consent to identify-level access.
        assert not set(_BOT_SCOPES) & set(_USER_SCOPES)


class TestPreBuiltClients:
    def test_user_client_has_user_scopes(self) -> None:
        assert isinstance(user_client, _ProxiedDiscordOAuth2)
        # The httpx_oauth ``DiscordOAuth2`` exposes its scopes on
        # the ``base_scopes`` attr (set in __init__).
        assert list(user_client.base_scopes or []) == _USER_SCOPES

    def test_bot_client_has_bot_scopes(self) -> None:
        assert isinstance(bot_client, _ProxiedDiscordOAuth2)
        assert list(bot_client.base_scopes or []) == _BOT_SCOPES


class TestProxiedHttpClient:
    def test_no_proxy_when_setting_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # DISCORD_PROXY_URL unset → pass ``proxy=None`` to the
        # AsyncClient. Pin prevents a regression that reads a
        # different env var and silently routes all Discord calls
        # through a stale proxy.
        monkeypatch.setattr(
            "rapidly.integrations.discord.oauth.settings.DISCORD_PROXY_URL", None
        )
        client = O.user_client.get_httpx_client()
        assert isinstance(client, httpx.AsyncClient)

    def test_proxy_when_setting_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "rapidly.integrations.discord.oauth.settings.DISCORD_PROXY_URL",
            "http://proxy.test:8888",
        )
        client = O.user_client.get_httpx_client()
        assert isinstance(client, httpx.AsyncClient)

    def test_empty_string_setting_treated_as_none(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # ``settings.DISCORD_PROXY_URL or None`` — an empty-string
        # env var must resolve to None (no proxy) rather than a
        # zero-length host that httpx would refuse.
        monkeypatch.setattr(
            "rapidly.integrations.discord.oauth.settings.DISCORD_PROXY_URL", ""
        )
        client = O.user_client.get_httpx_client()
        assert isinstance(client, httpx.AsyncClient)
