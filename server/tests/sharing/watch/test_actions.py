"""Tests for the Watch chamber backend (PR 9).

Same coverage shape as the Screen test suite — business logic end-to-end
against fakeredis plus the signaling-validator registration check.
"""

from __future__ import annotations

import pytest

# Register ("watch", "host") and ("watch", "guest") at import time.
import rapidly.sharing.watch.signaling_validators  # noqa: F401
from rapidly.redis import Redis
from rapidly.sharing.file_sharing.queries import (
    SESSION_KINDS,
    ChannelData,
    ChannelRepository,
    validate_session_kind,
)
from rapidly.sharing.file_sharing.signaling import _AUTH_VALIDATORS
from rapidly.sharing.watch import actions as watch_service


class TestSessionKindExtension:
    def test_watch_is_a_registered_kind(self) -> None:
        assert "watch" in SESSION_KINDS

    def test_validate_session_kind_accepts_watch(self) -> None:
        validate_session_kind("watch")  # must not raise

    def test_file_and_screen_still_supported(self) -> None:
        assert {"file", "screen"}.issubset(SESSION_KINDS)


class TestChannelDataWatchRoundtrip:
    def test_watch_defaults_match_file_shape(self) -> None:
        channel = ChannelData(secret="s", long_slug="l", short_slug="sh")
        assert channel.session_kind == "file"
        assert channel.watch_source_url is None
        assert channel.watch_source_kind == "url"
        assert channel.watch_started_at is None

    def test_roundtrip_preserves_watch_fields(self) -> None:
        channel = ChannelData(
            secret="s",
            long_slug="l",
            short_slug="sh",
            session_kind="watch",
            max_viewers=8,
            watch_source_url="https://example.com/video.mp4",
            watch_source_kind="url",
            watch_started_at="2026-04-18T10:00:00+00:00",
        )
        reloaded = ChannelData.from_dict(channel.to_dict())
        assert reloaded.session_kind == "watch"
        assert reloaded.max_viewers == 8
        assert reloaded.watch_source_url == "https://example.com/video.mp4"
        assert reloaded.watch_started_at == "2026-04-18T10:00:00+00:00"

    def test_legacy_payload_reads_with_watch_defaults(self) -> None:
        payload = {"secret": "h", "long_slug": "l", "short_slug": "sh"}
        reloaded = ChannelData.from_dict(payload)
        assert reloaded.watch_source_url is None
        assert reloaded.watch_source_kind == "url"
        assert reloaded.watch_started_at is None


class TestSignalingValidatorsRegistered:
    def test_watch_host_validator_registered(self) -> None:
        assert ("watch", "host") in _AUTH_VALIDATORS

    def test_watch_guest_validator_registered(self) -> None:
        assert ("watch", "guest") in _AUTH_VALIDATORS


@pytest.mark.asyncio
class TestCreateWatchSession:
    async def test_creates_session_with_watch_kind(self, redis: Redis) -> None:
        channel, raw_secret = await watch_service.create_watch_session(
            redis,
            title="Movie night",
            max_viewers=5,
            source_url="https://example.com/trailer.mp4",
        )
        assert channel.session_kind == "watch"
        assert channel.max_viewers == 5
        assert channel.title == "Movie night"
        assert channel.watch_source_url == "https://example.com/trailer.mp4"
        assert channel.watch_source_kind == "url"
        assert channel.watch_started_at is not None
        assert raw_secret

    async def test_roundtrips_through_channel_repo(self, redis: Redis) -> None:
        channel, _ = await watch_service.create_watch_session(
            redis, title=None, max_viewers=10, source_url=None
        )
        repo = ChannelRepository(redis)
        reloaded = await repo.fetch_channel(channel.short_slug)
        assert reloaded is not None
        assert reloaded.session_kind == "watch"

    async def test_accepts_null_source_url(self, redis: Redis) -> None:
        """Host can create the session first and set the URL later."""
        channel, _ = await watch_service.create_watch_session(
            redis, title=None, max_viewers=3, source_url=None
        )
        assert channel.watch_source_url is None


@pytest.mark.asyncio
class TestInviteTokens:
    async def test_mint_and_validate_happy_path(self, redis: Redis) -> None:
        channel, secret = await watch_service.create_watch_session(
            redis, title=None, max_viewers=3, source_url=None
        )
        token = await watch_service.mint_invite_token(redis, channel.short_slug, secret)
        assert token is not None
        assert (
            await watch_service.validate_invite_token(redis, channel.short_slug, token)
            is True
        )

    async def test_mint_rejects_wrong_secret(self, redis: Redis) -> None:
        channel, _ = await watch_service.create_watch_session(
            redis, title=None, max_viewers=3, source_url=None
        )
        assert (
            await watch_service.mint_invite_token(redis, channel.short_slug, "wrong")
            is None
        )

    async def test_validate_rejects_unknown_token(self, redis: Redis) -> None:
        channel, _ = await watch_service.create_watch_session(
            redis, title=None, max_viewers=3, source_url=None
        )
        assert (
            await watch_service.validate_invite_token(redis, channel.short_slug, "nope")
            is False
        )

    async def test_mint_refuses_screen_channel(self, redis: Redis) -> None:
        """Security: minting for a Screen-kind channel must not leak tokens
        usable against the Watch chamber's validators."""
        from rapidly.sharing.screen import actions as screen_service

        channel, secret = await screen_service.create_screen_session(
            redis, title=None, max_viewers=3
        )
        assert (
            await watch_service.mint_invite_token(redis, channel.short_slug, secret)
            is None
        )


@pytest.mark.asyncio
class TestGetPublicView:
    async def test_returns_public_view_for_watch_session(self, redis: Redis) -> None:
        channel, _ = await watch_service.create_watch_session(
            redis,
            title="Trailer",
            max_viewers=6,
            source_url="https://example.com/x.mp4",
        )
        view = await watch_service.get_public_view(redis, channel.short_slug)
        assert view is not None
        assert view["short_slug"] == channel.short_slug
        assert view["title"] == "Trailer"
        assert view["max_viewers"] == 6
        assert view["source_url"] == "https://example.com/x.mp4"
        assert view["source_kind"] == "url"
        assert "secret" not in view
        assert "invite_token" not in view

    async def test_returns_none_for_non_watch_session(self, redis: Redis) -> None:
        repo = ChannelRepository(redis)
        channel, _ = await repo.create_channel(ttl=600)
        assert await watch_service.get_public_view(redis, channel.short_slug) is None

    async def test_returns_none_for_unknown_slug(self, redis: Redis) -> None:
        assert await watch_service.get_public_view(redis, "nope") is None


@pytest.mark.asyncio
class TestCloseWatchSession:
    async def test_closes_with_correct_secret(self, redis: Redis) -> None:
        channel, secret = await watch_service.create_watch_session(
            redis, title=None, max_viewers=3, source_url=None
        )
        assert (
            await watch_service.close_watch_session(redis, channel.short_slug, secret)
            is True
        )
        repo = ChannelRepository(redis)
        assert await repo.fetch_channel(channel.short_slug) is None

    async def test_rejects_wrong_secret(self, redis: Redis) -> None:
        channel, _ = await watch_service.create_watch_session(
            redis, title=None, max_viewers=3, source_url=None
        )
        assert (
            await watch_service.close_watch_session(redis, channel.short_slug, "wrong")
            is False
        )

    async def test_refuses_to_close_file_session(self, redis: Redis) -> None:
        """Security invariant: Watch close must not destroy a file channel."""
        repo = ChannelRepository(redis)
        channel, secret = await repo.create_channel(ttl=600)
        assert (
            await watch_service.close_watch_session(redis, channel.short_slug, secret)
            is False
        )
        assert await repo.fetch_channel(channel.short_slug) is not None
