"""Tests for the Screen chamber backend (PR 5).

Covers the business-logic layer (create_screen_session, mint/validate
invite tokens, get_public_view, close_screen_session) end-to-end
against fakeredis. Signaling-validator registration is verified through
the dispatch key check (the registry is shared with file_sharing).
"""

from __future__ import annotations

import pytest

# Import for the side-effect of registering ("screen", "host") and
# ("screen", "guest") in the global auth validator registry.
import rapidly.sharing.screen.signaling_validators  # noqa: F401
from rapidly.redis import Redis
from rapidly.sharing.file_sharing.queries import (
    SESSION_KINDS,
    ChannelData,
    ChannelRepository,
    validate_session_kind,
)
from rapidly.sharing.file_sharing.signaling import _AUTH_VALIDATORS
from rapidly.sharing.screen import actions as screen_service


class TestSessionKindExtension:
    def test_screen_is_a_registered_kind(self) -> None:
        assert "screen" in SESSION_KINDS

    def test_validate_session_kind_accepts_screen(self) -> None:
        validate_session_kind("screen")  # must not raise

    def test_file_still_supported(self) -> None:
        assert "file" in SESSION_KINDS
        validate_session_kind("file")


class TestChannelDataScreenRoundtrip:
    def test_screen_defaults_match_file_shape(self) -> None:
        channel = ChannelData(secret="s", long_slug="l", short_slug="sh")
        assert channel.session_kind == "file"
        assert channel.max_viewers == 0
        assert channel.screen_started_at is None

    def test_roundtrip_preserves_screen_fields(self) -> None:
        channel = ChannelData(
            secret="s",
            long_slug="l",
            short_slug="sh",
            session_kind="screen",
            max_viewers=10,
            screen_started_at="2026-04-17T20:00:00+00:00",
        )
        reloaded = ChannelData.from_dict(channel.to_dict())
        assert reloaded.session_kind == "screen"
        assert reloaded.max_viewers == 10
        assert reloaded.screen_started_at == "2026-04-17T20:00:00+00:00"

    def test_legacy_payload_reads_with_screen_defaults(self) -> None:
        payload = {
            "secret": "h",
            "long_slug": "l",
            "short_slug": "sh",
        }
        reloaded = ChannelData.from_dict(payload)
        assert reloaded.session_kind == "file"
        assert reloaded.max_viewers == 0
        assert reloaded.screen_started_at is None


class TestSignalingValidatorsRegistered:
    def test_screen_host_validator_registered(self) -> None:
        assert ("screen", "host") in _AUTH_VALIDATORS

    def test_screen_guest_validator_registered(self) -> None:
        assert ("screen", "guest") in _AUTH_VALIDATORS


@pytest.mark.asyncio
class TestCreateScreenSession:
    async def test_creates_session_with_screen_kind(self, redis: Redis) -> None:
        channel, raw_secret = await screen_service.create_screen_session(
            redis, title="Demo", max_viewers=5
        )
        assert channel.session_kind == "screen"
        assert channel.max_viewers == 5
        assert channel.title == "Demo"
        assert channel.screen_started_at is not None
        assert raw_secret  # non-empty

    async def test_roundtrips_through_channel_repo(self, redis: Redis) -> None:
        channel, _ = await screen_service.create_screen_session(
            redis, title=None, max_viewers=10
        )
        repo = ChannelRepository(redis)
        reloaded = await repo.fetch_channel(channel.short_slug)
        assert reloaded is not None
        assert reloaded.session_kind == "screen"
        assert reloaded.max_viewers == 10


@pytest.mark.asyncio
class TestInviteTokens:
    async def test_mint_and_validate_happy_path(self, redis: Redis) -> None:
        channel, secret = await screen_service.create_screen_session(
            redis, title=None, max_viewers=3
        )
        token = await screen_service.mint_invite_token(
            redis, channel.short_slug, secret
        )
        assert token is not None
        assert (
            await screen_service.validate_invite_token(redis, channel.short_slug, token)
            is True
        )

    async def test_mint_rejects_wrong_secret(self, redis: Redis) -> None:
        channel, _ = await screen_service.create_screen_session(
            redis, title=None, max_viewers=3
        )
        token = await screen_service.mint_invite_token(
            redis, channel.short_slug, "wrong-secret"
        )
        assert token is None

    async def test_validate_rejects_unknown_token(self, redis: Redis) -> None:
        channel, _ = await screen_service.create_screen_session(
            redis, title=None, max_viewers=3
        )
        assert (
            await screen_service.validate_invite_token(
                redis, channel.short_slug, "not-a-real-token"
            )
            is False
        )

    async def test_validate_rejects_empty_token(self, redis: Redis) -> None:
        assert (
            await screen_service.validate_invite_token(redis, "any-slug", "") is False
        )

    async def test_mint_returns_none_for_file_session(self, redis: Redis) -> None:
        """The screen mint path must refuse to mint for file channels.

        Prevents cross-chamber confusion if the wrong slug is passed.
        """
        repo = ChannelRepository(redis)
        channel, secret = await repo.create_channel(ttl=600)
        # channel.session_kind is "file" by default.
        assert (
            await screen_service.mint_invite_token(redis, channel.short_slug, secret)
            is None
        )


@pytest.mark.asyncio
class TestGetPublicView:
    async def test_returns_public_view_for_screen_session(self, redis: Redis) -> None:
        channel, _ = await screen_service.create_screen_session(
            redis, title="Live Demo", max_viewers=7
        )
        view = await screen_service.get_public_view(redis, channel.short_slug)
        assert view is not None
        assert view["short_slug"] == channel.short_slug
        assert view["title"] == "Live Demo"
        assert view["max_viewers"] == 7
        assert view["started_at"] is not None
        # No secret / invite leak
        assert "secret" not in view
        assert "invite_token" not in view

    async def test_returns_none_for_file_session(self, redis: Redis) -> None:
        repo = ChannelRepository(redis)
        channel, _ = await repo.create_channel(ttl=600)
        view = await screen_service.get_public_view(redis, channel.short_slug)
        assert view is None

    async def test_returns_none_for_unknown_slug(self, redis: Redis) -> None:
        assert await screen_service.get_public_view(redis, "nonexistent") is None


@pytest.mark.asyncio
class TestCloseScreenSession:
    async def test_closes_with_correct_secret(self, redis: Redis) -> None:
        channel, secret = await screen_service.create_screen_session(
            redis, title=None, max_viewers=3
        )
        assert (
            await screen_service.close_screen_session(redis, channel.short_slug, secret)
            is True
        )
        # Channel should now be gone.
        repo = ChannelRepository(redis)
        assert await repo.fetch_channel(channel.short_slug) is None

    async def test_rejects_wrong_secret(self, redis: Redis) -> None:
        channel, _ = await screen_service.create_screen_session(
            redis, title=None, max_viewers=3
        )
        assert (
            await screen_service.close_screen_session(
                redis, channel.short_slug, "wrong"
            )
            is False
        )
        # Channel intact.
        repo = ChannelRepository(redis)
        assert await repo.fetch_channel(channel.short_slug) is not None

    async def test_returns_false_for_unknown_session(self, redis: Redis) -> None:
        assert (
            await screen_service.close_screen_session(redis, "nonexistent", "secret")
            is False
        )

    async def test_refuses_to_close_file_session(self, redis: Redis) -> None:
        """Security invariant: the screen close path must refuse to
        destroy a file channel even with the correct secret."""
        repo = ChannelRepository(redis)
        channel, secret = await repo.create_channel(ttl=600)
        assert (
            await screen_service.close_screen_session(redis, channel.short_slug, secret)
            is False
        )
        # File channel intact.
        assert await repo.fetch_channel(channel.short_slug) is not None
