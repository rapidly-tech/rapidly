"""Tests for ``rapidly/integrations/discord/client.py``.

Five load-bearing surfaces:

- ``BASE_URL`` is pinned to the Discord v10 API
  (``https://discord.com/api/v10``). Drift to a wrong major
  version would route every call to a deprecated / unstable
  endpoint set; drift to a non-Discord host would silently
  re-target our bot at someone else's API.
- The Authorization header uses the ``"<scheme> <token>"`` form
  with ``"Bot"`` or ``"Bearer"`` literal — drift would 401 the
  bot at startup.
- ``add_member`` posts the ``access_token`` + ``roles=[role_id]``
  payload (with optional ``nick``). Drift to swap key names
  would cause Discord to silently ignore the payload (no role
  assigned, no error returned at our layer).
- ``add_member`` HTTP 201 → success; HTTP 200/204 (member
  already present) → fall through to ``add_member_role``. Drift
  would either refuse to re-promote existing members or
  double-add roles on every retry.
- ``remove_member_role`` and ``remove_member`` use DELETE on the
  documented Discord endpoints — drift to PATCH/POST would
  silently no-op against Discord.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from rapidly.integrations.discord import client as M
from rapidly.integrations.discord.client import BASE_URL, DiscordClient


def _make_client(*, scheme: str = "Bot", token: str = "test_token") -> DiscordClient:
    return DiscordClient(scheme=scheme, token=token)  # type: ignore[arg-type]


class TestBaseUrl:
    def test_pinned_to_v10(self) -> None:
        # Pin: Discord API v10 — drift to a different major
        # version (or non-Discord host) would silently retarget
        # every bot call.
        assert BASE_URL == "https://discord.com/api/v10"

    def test_client_base_url_uses_pinned_constant(self) -> None:
        client = _make_client()
        assert str(client.client.base_url).startswith(BASE_URL)


class TestAuthorizationHeader:
    def test_bot_scheme_header_format(self) -> None:
        client = _make_client(scheme="Bot", token="abc123")
        auth = client.client.headers.get("authorization")
        assert auth == "Bot abc123"

    def test_bearer_scheme_header_format(self) -> None:
        # Pin: OAuth-flow callers pass scheme="Bearer". Drift to
        # always-Bot would 401 the user-token endpoints.
        client = _make_client(scheme="Bearer", token="user_token")
        auth = client.client.headers.get("authorization")
        assert auth == "Bearer user_token"


@pytest.mark.asyncio
class TestAddMember:
    async def _captured_request(
        self,
        client: DiscordClient,
        responses: list[httpx.Response],
    ) -> list[Any]:
        # Replace the AsyncClient with a mock that captures calls
        # and serves the supplied response sequence in order.
        calls: list[Any] = []

        async def _put(endpoint: str, **kwargs: Any) -> httpx.Response:
            calls.append(("PUT", endpoint, kwargs))
            return responses.pop(0)

        async def _delete(endpoint: str, **kwargs: Any) -> httpx.Response:
            calls.append(("DELETE", endpoint, kwargs))
            return responses.pop(0)

        client.client = MagicMock()
        client.client.put = AsyncMock(side_effect=_put)
        client.client.delete = AsyncMock(side_effect=_delete)
        return calls

    async def test_payload_uses_documented_keys(self) -> None:
        # Pin: the Discord PUT-member-to-guild endpoint requires
        # ``access_token`` + ``roles`` keys. Drift to camelCase
        # or alternative names would have Discord silently
        # ignore the payload (no role assigned, no error).
        client = _make_client()
        calls = await self._captured_request(
            client,
            [
                httpx.Response(
                    201, request=httpx.Request("PUT", "https://discord.com/x")
                )
            ],
        )

        await client.add_member(
            guild_id="g1",
            discord_user_id="u1",
            discord_user_access_token="user_token",
            role_id="r1",
        )

        method, endpoint, kwargs = calls[0]
        assert method == "PUT"
        assert endpoint == "/guilds/g1/members/u1"
        assert kwargs["json"] == {
            "access_token": "user_token",
            "roles": ["r1"],
        }

    async def test_optional_nick_included_when_passed(self) -> None:
        client = _make_client()
        calls = await self._captured_request(
            client,
            [
                httpx.Response(
                    201, request=httpx.Request("PUT", "https://discord.com/x")
                )
            ],
        )

        await client.add_member(
            guild_id="g1",
            discord_user_id="u1",
            discord_user_access_token="user_token",
            role_id="r1",
            nick="alice",
        )

        _, _, kwargs = calls[0]
        assert kwargs["json"]["nick"] == "alice"

    async def test_201_short_circuits_no_role_followup(self) -> None:
        # Pin: 201 = newly-added → DON'T follow up with
        # add_member_role. Drift to always-call would emit a
        # double role assignment on every fresh add (Discord
        # tolerates it, but it's wasted requests).
        client = _make_client()
        calls = await self._captured_request(
            client,
            [
                httpx.Response(
                    201, request=httpx.Request("PUT", "https://discord.com/x")
                )
            ],
        )

        await client.add_member(
            guild_id="g1",
            discord_user_id="u1",
            discord_user_access_token="user_token",
            role_id="r1",
        )

        # Exactly one PUT — to the member endpoint, NOT the role
        # endpoint.
        assert len(calls) == 1

    async def test_204_falls_through_to_add_member_role(self) -> None:
        # Pin: HTTP 204 (member already present) → fall through
        # to add_member_role. Drift to refuse on 204 would block
        # role updates for existing members; drift to swallow
        # silently would never assign the role to existing
        # users.
        client = _make_client()
        calls = await self._captured_request(
            client,
            [
                httpx.Response(
                    204, request=httpx.Request("PUT", "https://discord.com/x")
                ),
                httpx.Response(
                    204, request=httpx.Request("PUT", "https://discord.com/x")
                ),  # for add_member_role
            ],
        )

        await client.add_member(
            guild_id="g1",
            discord_user_id="u1",
            discord_user_access_token="user_token",
            role_id="r1",
        )

        # Two PUTs: member-endpoint + role-endpoint.
        assert len(calls) == 2
        assert calls[1][1] == "/guilds/g1/members/u1/roles/r1"


@pytest.mark.asyncio
class TestRoleManagementEndpoints:
    async def test_add_member_role_uses_put(self) -> None:
        client = _make_client()
        client.client = MagicMock()
        client.client.put = AsyncMock(
            return_value=httpx.Response(
                204, request=httpx.Request("PUT", "https://discord.com/x")
            )
        )

        await client.add_member_role(guild_id="g1", discord_user_id="u1", role_id="r1")

        client.client.put.assert_called_once_with("/guilds/g1/members/u1/roles/r1")

    async def test_remove_member_role_uses_delete(self) -> None:
        # Pin: role-removal is DELETE (NOT PATCH or POST). Drift
        # would silently no-op against Discord — the user keeps
        # the role they should have lost, which is a paid-tier
        # leak.
        client = _make_client()
        client.client = MagicMock()
        client.client.delete = AsyncMock(
            return_value=httpx.Response(
                204, request=httpx.Request("PUT", "https://discord.com/x")
            )
        )

        await client.remove_member_role(
            guild_id="g1", discord_user_id="u1", role_id="r1"
        )

        client.client.delete.assert_called_once_with("/guilds/g1/members/u1/roles/r1")

    async def test_remove_member_uses_delete(self) -> None:
        client = _make_client()
        client.client = MagicMock()
        client.client.delete = AsyncMock(
            return_value=httpx.Response(
                204, request=httpx.Request("PUT", "https://discord.com/x")
            )
        )

        await client.remove_member(guild_id="g1", discord_user_id="u1")

        client.client.delete.assert_called_once_with("/guilds/g1/members/u1")


@pytest.mark.asyncio
class TestRaiseOnError:
    async def test_4xx_raises_http_status_error(self) -> None:
        # Pin: HTTP errors propagate as ``HTTPStatusError`` so
        # callers can retry / fail loudly. Drift to swallow
        # would silently drop role-assignment failures.
        client = _make_client()
        client.client = MagicMock()
        client.client.get = AsyncMock(
            return_value=httpx.Response(
                403,
                request=httpx.Request("GET", "https://discord.com/api/v10/users/@me"),
            )
        )

        with pytest.raises(httpx.HTTPStatusError):
            await client.get_me()


class TestExports:
    def test_dunder_all_pinned(self) -> None:
        # Pin: ``DiscordClient`` (factory) + ``bot_client``
        # (process-singleton) are the documented exports. Drift
        # to add internal helpers would silently widen the API.
        assert set(M.__all__) == {"DiscordClient", "bot_client"}
