"""Tests for the Collab chamber backend (PR 16)."""

from __future__ import annotations

import pytest

import rapidly.sharing.markup.signaling_validators  # noqa: F401
from rapidly.redis import Redis
from rapidly.sharing.markup import actions as collab_service
from rapidly.sharing.file_sharing.queries import (
    SESSION_KINDS,
    ChannelData,
    ChannelRepository,
    validate_session_kind,
)
from rapidly.sharing.file_sharing.signaling import _AUTH_VALIDATORS


async def _make_sibling_channel(redis: Redis, kind: str) -> tuple[ChannelData, str]:
    """Create a channel for a non-Collab chamber using its own service.

    Post-M1.1 only ``"file"`` is left as a sibling kind — the media
    chambers (screen / watch / call) were removed. The remaining
    invariant (collab refuses to mint / close non-collab kinds) still
    matters because file_sharing channels coexist with collab channels
    in the same Redis namespace.
    """
    if kind == "file":
        return await ChannelRepository(redis).create_channel(ttl=600)
    raise ValueError(f"unknown sibling kind {kind!r}")


class TestSessionKindExtension:
    def test_collab_is_a_registered_kind(self) -> None:
        assert "collab" in SESSION_KINDS

    def test_validate_session_kind_accepts_collab(self) -> None:
        validate_session_kind("collab")  # must not raise

    def test_file_kind_still_supported(self) -> None:
        # file_sharing is the only sibling kind left after M1.1; screen
        # / watch / call were removed when their chambers were deleted.
        assert "file" in SESSION_KINDS


class TestChannelDataCollabRoundtrip:
    def test_collab_defaults_match_file_shape(self) -> None:
        channel = ChannelData(secret="s", long_slug="l", short_slug="sh")
        assert channel.session_kind == "file"
        assert channel.collab_kind == "text"
        assert channel.collab_started_at is None

    def test_roundtrip_preserves_collab_fields(self) -> None:
        channel = ChannelData(
            secret="s",
            long_slug="l",
            short_slug="sh",
            session_kind="collab",
            collab_kind="canvas",
            max_participants=6,
            collab_started_at="2026-04-18T12:00:00+00:00",
        )
        reloaded = ChannelData.from_dict(channel.to_dict())
        assert reloaded.session_kind == "collab"
        assert reloaded.collab_kind == "canvas"
        assert reloaded.max_participants == 6
        assert reloaded.collab_started_at == "2026-04-18T12:00:00+00:00"

    def test_legacy_payload_reads_with_collab_defaults(self) -> None:
        payload = {"secret": "h", "long_slug": "l", "short_slug": "sh"}
        reloaded = ChannelData.from_dict(payload)
        assert reloaded.collab_kind == "text"
        assert reloaded.collab_started_at is None


class TestSignalingValidatorsRegistered:
    def test_collab_host_validator_registered(self) -> None:
        assert ("collab", "host") in _AUTH_VALIDATORS

    def test_collab_guest_validator_registered(self) -> None:
        assert ("collab", "guest") in _AUTH_VALIDATORS


@pytest.mark.asyncio
class TestCreateCollabSession:
    async def test_creates_session_with_collab_kind(self, redis: Redis) -> None:
        channel, raw_secret = await collab_service.create_collab_session(
            redis, title="Notes", max_participants=4
        )
        assert channel.session_kind == "collab"
        assert channel.max_participants == 4
        assert channel.collab_kind == "text"
        assert channel.title == "Notes"
        assert channel.collab_started_at is not None
        assert raw_secret

    async def test_canvas_kind_supported(self, redis: Redis) -> None:
        channel, _ = await collab_service.create_collab_session(
            redis, title=None, max_participants=3, kind="canvas"
        )
        assert channel.collab_kind == "canvas"

    async def test_roundtrips_through_channel_repo(self, redis: Redis) -> None:
        channel, _ = await collab_service.create_collab_session(
            redis, title=None, max_participants=2
        )
        repo = ChannelRepository(redis)
        reloaded = await repo.fetch_channel(channel.short_slug)
        assert reloaded is not None
        assert reloaded.session_kind == "collab"


@pytest.mark.asyncio
class TestInviteTokens:
    async def test_mint_and_validate_happy_path(self, redis: Redis) -> None:
        channel, secret = await collab_service.create_collab_session(
            redis, title=None, max_participants=4
        )
        token = await collab_service.mint_invite_token(
            redis, channel.short_slug, secret
        )
        assert token is not None
        assert (
            await collab_service.validate_invite_token(redis, channel.short_slug, token)
            is True
        )

    async def test_mint_rejects_wrong_secret(self, redis: Redis) -> None:
        channel, _ = await collab_service.create_collab_session(
            redis, title=None, max_participants=4
        )
        assert (
            await collab_service.mint_invite_token(redis, channel.short_slug, "wrong")
            is None
        )

    async def test_validate_rejects_unknown_token(self, redis: Redis) -> None:
        channel, _ = await collab_service.create_collab_session(
            redis, title=None, max_participants=4
        )
        assert (
            await collab_service.validate_invite_token(
                redis, channel.short_slug, "nope"
            )
            is False
        )

    @pytest.mark.parametrize("sibling_kind", ["file"])
    async def test_mint_refuses_every_sibling_kind(
        self, redis: Redis, sibling_kind: str
    ) -> None:
        """Defense-in-depth: mint must refuse every existing non-collab kind.

        Pinning the invariant once per sibling means adding a new
        session_kind in a future PR cannot silently widen the surface
        area — the test must be updated explicitly. Post-M1.1 only
        ``file`` remains as a sibling kind; the per-kind test for
        ``call`` was removed when the chamber was deleted.
        """
        channel, secret = await _make_sibling_channel(redis, sibling_kind)
        assert (
            await collab_service.mint_invite_token(redis, channel.short_slug, secret)
            is None
        )


@pytest.mark.asyncio
class TestGetPublicView:
    async def test_returns_public_view_for_collab_session(self, redis: Redis) -> None:
        channel, _ = await collab_service.create_collab_session(
            redis, title="Sprint notes", max_participants=5, kind="text"
        )
        view = await collab_service.get_public_view(redis, channel.short_slug)
        assert view is not None
        assert view["short_slug"] == channel.short_slug
        assert view["title"] == "Sprint notes"
        assert view["max_participants"] == 5
        assert view["kind"] == "text"
        assert "secret" not in view

    async def test_returns_none_for_file_session(self, redis: Redis) -> None:
        # file_sharing channels are the only remaining non-collab kind
        # after M1.1. The invariant (get_public_view returns None for
        # non-collab kinds) still holds; the call/watch-flavored tests
        # were removed with their chambers.
        channel, _ = await ChannelRepository(redis).create_channel(ttl=600)
        assert await collab_service.get_public_view(redis, channel.short_slug) is None

    async def test_returns_none_for_unknown_slug(self, redis: Redis) -> None:
        assert await collab_service.get_public_view(redis, "nope") is None


@pytest.mark.asyncio
class TestCloseCollabSession:
    async def test_closes_with_correct_secret(self, redis: Redis) -> None:
        channel, secret = await collab_service.create_collab_session(
            redis, title=None, max_participants=3
        )
        assert (
            await collab_service.close_collab_session(redis, channel.short_slug, secret)
            is True
        )
        repo = ChannelRepository(redis)
        assert await repo.fetch_channel(channel.short_slug) is None

    async def test_rejects_wrong_secret(self, redis: Redis) -> None:
        channel, _ = await collab_service.create_collab_session(
            redis, title=None, max_participants=3
        )
        assert (
            await collab_service.close_collab_session(
                redis, channel.short_slug, "wrong"
            )
            is False
        )

    async def test_refuses_to_close_file_session(self, redis: Redis) -> None:
        """Security invariant: Collab close must not destroy a file channel."""
        repo = ChannelRepository(redis)
        channel, secret = await repo.create_channel(ttl=600)
        assert (
            await collab_service.close_collab_session(redis, channel.short_slug, secret)
            is False
        )
        assert await repo.fetch_channel(channel.short_slug) is not None

    @pytest.mark.parametrize(
        "sibling_kind",
        ["file"],
    )
    async def test_close_refuses_every_sibling_kind(
        self, redis: Redis, sibling_kind: str
    ) -> None:
        """Defense-in-depth: close must refuse every existing chamber kind."""
        channel, secret = await _make_sibling_channel(redis, sibling_kind)
        assert (
            await collab_service.close_collab_session(redis, channel.short_slug, secret)
            is False
        )
        # Channel must still exist — close refused, nothing destroyed.
        assert await ChannelRepository(redis).fetch_channel(channel.short_slug)
