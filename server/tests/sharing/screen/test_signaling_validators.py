"""Auth-validator tests for ``session_kind="screen"``.

Covers the two registered validators end-to-end against FakeRedis: the
host path (channel-secret HMAC compare) and the guest path (invite-token
SISMEMBER). The dispatch shape is already covered by
``tests/sharing/file_sharing/test_signaling_auth.py``; this module
asserts screen-specific behaviour — including the generic auth-failed
error + 4003 close code on failure, which is a security-relevant
contract that the file-sharing validators also uphold.
"""

from __future__ import annotations

from typing import Any

import pytest

# Import for the registration side-effect (screen host + guest validators).
import rapidly.sharing.screen.signaling_validators  # noqa: F401
from rapidly.sharing.file_sharing.queries import ChannelRepository
from rapidly.sharing.file_sharing.signaling import _AUTH_VALIDATORS, AuthContext
from rapidly.sharing.screen import actions as screen_service


class _MockWs:
    """Minimal WebSocket stand-in for validator tests."""

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
class TestScreenHostValidator:
    async def test_valid_host_secret_passes(self, redis: Any) -> None:
        channel, secret = await screen_service.create_screen_session(
            redis, title=None, max_viewers=3
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
        validator = _AUTH_VALIDATORS[("screen", "host")]
        assert await validator(ctx) is True

    async def test_wrong_host_secret_fails_with_close_4003(self, redis: Any) -> None:
        channel, _ = await screen_service.create_screen_session(
            redis, title=None, max_viewers=3
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
        validator = _AUTH_VALIDATORS[("screen", "host")]
        assert await validator(ctx) is False
        assert ws.closed is True
        assert ws.close_code == 4003
        # Generic error — no distinction between "wrong secret" and
        # "session doesn't exist" so attackers can't enumerate slugs.
        assert any("Authentication failed" in msg for msg in ws.sent)

    async def test_missing_secret_field_fails(self, redis: Any) -> None:
        channel, _ = await screen_service.create_screen_session(
            redis, title=None, max_viewers=3
        )
        repo = ChannelRepository(redis)
        ws = _MockWs()
        ctx = AuthContext(
            ws=ws,  # type: ignore[arg-type]
            slug=channel.short_slug,
            role="host",
            channel=channel,
            msg={"type": "auth", "role": "host"},  # no secret
            repo=repo,
            client_ip="127.0.0.1",
        )
        validator = _AUTH_VALIDATORS[("screen", "host")]
        assert await validator(ctx) is False
        assert ws.close_code == 4003


@pytest.mark.asyncio
class TestScreenGuestValidator:
    async def test_valid_invite_token_passes(self, redis: Any) -> None:
        channel, secret = await screen_service.create_screen_session(
            redis, title=None, max_viewers=3
        )
        token = await screen_service.mint_invite_token(
            redis, channel.short_slug, secret
        )
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
        validator = _AUTH_VALIDATORS[("screen", "guest")]
        assert await validator(ctx) is True

    async def test_unknown_invite_token_fails_with_close_4003(self, redis: Any) -> None:
        channel, _ = await screen_service.create_screen_session(
            redis, title=None, max_viewers=3
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
        validator = _AUTH_VALIDATORS[("screen", "guest")]
        assert await validator(ctx) is False
        assert ws.closed is True
        assert ws.close_code == 4003
        assert any("Authentication failed" in msg for msg in ws.sent)

    async def test_missing_token_field_fails(self, redis: Any) -> None:
        channel, _ = await screen_service.create_screen_session(
            redis, title=None, max_viewers=3
        )
        repo = ChannelRepository(redis)
        ws = _MockWs()
        ctx = AuthContext(
            ws=ws,  # type: ignore[arg-type]
            slug=channel.short_slug,
            role="guest",
            channel=channel,
            msg={"type": "auth", "role": "guest"},
            repo=repo,
            client_ip="127.0.0.1",
        )
        validator = _AUTH_VALIDATORS[("screen", "guest")]
        assert await validator(ctx) is False
        assert ws.close_code == 4003
