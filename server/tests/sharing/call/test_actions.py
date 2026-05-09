"""Tests for the Call chamber backend (PR 13)."""

from __future__ import annotations

import pytest

import rapidly.sharing.call.signaling_validators  # noqa: F401
from rapidly.redis import Redis
from rapidly.sharing.call import actions as call_service
from rapidly.sharing.file_sharing.queries import (
    SESSION_KINDS,
    ChannelData,
    ChannelRepository,
    validate_session_kind,
)
from rapidly.sharing.file_sharing.signaling import _AUTH_VALIDATORS


class TestSessionKindExtension:
    def test_call_is_a_registered_kind(self) -> None:
        assert "call" in SESSION_KINDS

    def test_validate_session_kind_accepts_call(self) -> None:
        validate_session_kind("call")  # must not raise

    def test_existing_kinds_still_supported(self) -> None:
        assert {"file", "screen", "watch"}.issubset(SESSION_KINDS)


class TestChannelDataCallRoundtrip:
    def test_call_defaults_match_file_shape(self) -> None:
        channel = ChannelData(secret="s", long_slug="l", short_slug="sh")
        assert channel.session_kind == "file"
        assert channel.call_mode == "audio_video"
        assert channel.max_participants == 0
        assert channel.call_started_at is None

    def test_roundtrip_preserves_call_fields(self) -> None:
        channel = ChannelData(
            secret="s",
            long_slug="l",
            short_slug="sh",
            session_kind="call",
            call_mode="audio_only",
            max_participants=3,
            call_started_at="2026-04-18T12:00:00+00:00",
        )
        reloaded = ChannelData.from_dict(channel.to_dict())
        assert reloaded.session_kind == "call"
        assert reloaded.call_mode == "audio_only"
        assert reloaded.max_participants == 3
        assert reloaded.call_started_at == "2026-04-18T12:00:00+00:00"

    def test_legacy_payload_reads_with_call_defaults(self) -> None:
        payload = {"secret": "h", "long_slug": "l", "short_slug": "sh"}
        reloaded = ChannelData.from_dict(payload)
        assert reloaded.call_mode == "audio_video"
        assert reloaded.max_participants == 0


class TestSignalingValidatorsRegistered:
    def test_call_host_validator_registered(self) -> None:
        assert ("call", "host") in _AUTH_VALIDATORS

    def test_call_guest_validator_registered(self) -> None:
        assert ("call", "guest") in _AUTH_VALIDATORS


@pytest.mark.asyncio
class TestCreateCallSession:
    async def test_creates_session_with_call_kind(self, redis: Redis) -> None:
        channel, raw_secret = await call_service.create_call_session(
            redis, title="Team standup", max_participants=4
        )
        assert channel.session_kind == "call"
        assert channel.max_participants == 4
        assert channel.call_mode == "audio_video"
        assert channel.title == "Team standup"
        assert channel.call_started_at is not None
        assert raw_secret

    async def test_roundtrips_through_channel_repo(self, redis: Redis) -> None:
        channel, _ = await call_service.create_call_session(
            redis, title=None, max_participants=2, mode="audio_only"
        )
        repo = ChannelRepository(redis)
        reloaded = await repo.fetch_channel(channel.short_slug)
        assert reloaded is not None
        assert reloaded.session_kind == "call"
        assert reloaded.call_mode == "audio_only"


@pytest.mark.asyncio
class TestInviteTokens:
    async def test_mint_and_validate_happy_path(self, redis: Redis) -> None:
        channel, secret = await call_service.create_call_session(
            redis, title=None, max_participants=3
        )
        token = await call_service.mint_invite_token(redis, channel.short_slug, secret)
        assert token is not None
        assert (
            await call_service.validate_invite_token(redis, channel.short_slug, token)
            is True
        )

    async def test_mint_rejects_wrong_secret(self, redis: Redis) -> None:
        channel, _ = await call_service.create_call_session(
            redis, title=None, max_participants=3
        )
        assert (
            await call_service.mint_invite_token(redis, channel.short_slug, "wrong")
            is None
        )

    async def test_validate_rejects_unknown_token(self, redis: Redis) -> None:
        channel, _ = await call_service.create_call_session(
            redis, title=None, max_participants=3
        )
        assert (
            await call_service.validate_invite_token(redis, channel.short_slug, "nope")
            is False
        )

    async def test_mint_refuses_watch_channel(self, redis: Redis) -> None:
        """Security: mint for a non-Call channel kind must return None."""
        from rapidly.sharing.watch import actions as watch_service

        channel, secret = await watch_service.create_watch_session(
            redis, title=None, max_viewers=3, source_url=None
        )
        assert (
            await call_service.mint_invite_token(redis, channel.short_slug, secret)
            is None
        )


@pytest.mark.asyncio
class TestGetPublicView:
    async def test_returns_public_view_for_call_session(self, redis: Redis) -> None:
        channel, _ = await call_service.create_call_session(
            redis, title="Daily", max_participants=4, mode="audio_video"
        )
        view = await call_service.get_public_view(redis, channel.short_slug)
        assert view is not None
        assert view["short_slug"] == channel.short_slug
        assert view["title"] == "Daily"
        assert view["max_participants"] == 4
        assert view["mode"] == "audio_video"
        assert "secret" not in view

    async def test_returns_none_for_screen_session(self, redis: Redis) -> None:
        from rapidly.sharing.screen import actions as screen_service

        channel, _ = await screen_service.create_screen_session(
            redis, title=None, max_viewers=3
        )
        assert await call_service.get_public_view(redis, channel.short_slug) is None

    async def test_returns_none_for_unknown_slug(self, redis: Redis) -> None:
        assert await call_service.get_public_view(redis, "nope") is None


@pytest.mark.asyncio
class TestCloseCallSession:
    async def test_closes_with_correct_secret(self, redis: Redis) -> None:
        channel, secret = await call_service.create_call_session(
            redis, title=None, max_participants=3
        )
        assert (
            await call_service.close_call_session(redis, channel.short_slug, secret)
            is True
        )
        repo = ChannelRepository(redis)
        assert await repo.fetch_channel(channel.short_slug) is None

    async def test_rejects_wrong_secret(self, redis: Redis) -> None:
        channel, _ = await call_service.create_call_session(
            redis, title=None, max_participants=3
        )
        assert (
            await call_service.close_call_session(redis, channel.short_slug, "wrong")
            is False
        )

    async def test_refuses_to_close_file_session(self, redis: Redis) -> None:
        """Security invariant: Call close must not destroy a file channel."""
        repo = ChannelRepository(redis)
        channel, secret = await repo.create_channel(ttl=600)
        assert (
            await call_service.close_call_session(redis, channel.short_slug, secret)
            is False
        )
        assert await repo.fetch_channel(channel.short_slug) is not None
