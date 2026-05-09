"""Auth-validator tests for ``session_kind="watch"``."""

from __future__ import annotations

from typing import Any

import pytest

# Register the validators at import time.
import rapidly.sharing.watch.signaling_validators  # noqa: F401
from rapidly.sharing.file_sharing.queries import ChannelRepository
from rapidly.sharing.file_sharing.signaling import _AUTH_VALIDATORS, AuthContext
from rapidly.sharing.watch import actions as watch_service


class _MockWs:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.closed: bool = False
        self.close_code: int | None = None
        self.cookies: dict[str, str] = {}

    async def send_text(self, data: str) -> None:
        self.sent.append(data)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = True
        self.close_code = code


@pytest.mark.asyncio
class TestWatchHostValidator:
    async def test_valid_host_secret_passes(self, redis: Any) -> None:
        channel, secret = await watch_service.create_watch_session(
            redis, title=None, max_viewers=3, source_url=None
        )
        repo = ChannelRepository(redis)
        ctx = AuthContext(
            ws=_MockWs(),  # type: ignore[arg-type]
            slug=channel.short_slug,
            role="host",
            channel=channel,
            msg={"type": "auth", "role": "host", "secret": secret},
            repo=repo,
            client_ip="127.0.0.1",
        )
        assert await _AUTH_VALIDATORS[("watch", "host")](ctx) is True

    async def test_wrong_host_secret_fails_4003(self, redis: Any) -> None:
        channel, _ = await watch_service.create_watch_session(
            redis, title=None, max_viewers=3, source_url=None
        )
        repo = ChannelRepository(redis)
        ws = _MockWs()
        ctx = AuthContext(
            ws=ws,  # type: ignore[arg-type]
            slug=channel.short_slug,
            role="host",
            channel=channel,
            msg={"type": "auth", "role": "host", "secret": "wrong"},
            repo=repo,
            client_ip="127.0.0.1",
        )
        assert await _AUTH_VALIDATORS[("watch", "host")](ctx) is False
        assert ws.closed is True
        assert ws.close_code == 4003
        assert any("Authentication failed" in m for m in ws.sent)


@pytest.mark.asyncio
class TestWatchGuestValidator:
    async def test_valid_invite_token_passes(self, redis: Any) -> None:
        channel, secret = await watch_service.create_watch_session(
            redis, title=None, max_viewers=3, source_url=None
        )
        token = await watch_service.mint_invite_token(redis, channel.short_slug, secret)
        assert token is not None
        repo = ChannelRepository(redis)
        ctx = AuthContext(
            ws=_MockWs(),  # type: ignore[arg-type]
            slug=channel.short_slug,
            role="guest",
            channel=channel,
            msg={"type": "auth", "role": "guest", "token": token},
            repo=repo,
            client_ip="127.0.0.1",
        )
        assert await _AUTH_VALIDATORS[("watch", "guest")](ctx) is True

    async def test_unknown_invite_fails_4003(self, redis: Any) -> None:
        channel, _ = await watch_service.create_watch_session(
            redis, title=None, max_viewers=3, source_url=None
        )
        repo = ChannelRepository(redis)
        ws = _MockWs()
        ctx = AuthContext(
            ws=ws,  # type: ignore[arg-type]
            slug=channel.short_slug,
            role="guest",
            channel=channel,
            msg={"type": "auth", "role": "guest", "token": "not-real"},
            repo=repo,
            client_ip="127.0.0.1",
        )
        assert await _AUTH_VALIDATORS[("watch", "guest")](ctx) is False
        assert ws.closed is True
        assert ws.close_code == 4003
