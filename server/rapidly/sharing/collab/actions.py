"""Business logic for the Collab chamber."""

from __future__ import annotations

import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta

import structlog

from rapidly.config import settings
from rapidly.redis import Redis
from rapidly.sharing.file_sharing.queries import (
    ChannelData,
    ChannelRepository,
    _hash_secret,
)

from .queries import InviteTokenRepository

_log = structlog.get_logger(__name__)


_INVITE_TOKEN_BYTES = 32

# Collab sessions often run longer than calls (standups, writing
# sessions, planning). Default 2h; host can recreate for longer.
COLLAB_SESSION_TTL = 7200


async def create_collab_session(
    redis: Redis,
    *,
    title: str | None,
    max_participants: int,
    kind: str = "text",
    user_id: str | None = None,
) -> tuple[ChannelData, str]:
    """Create a new Collab session. Returns (channel, raw_secret)."""
    repo = ChannelRepository(redis)
    now_iso = datetime.now(UTC).isoformat()
    channel, raw_secret = await repo.create_channel(
        max_downloads=0,
        ttl=COLLAB_SESSION_TTL,
        title=title,
        user_id=user_id,
    )
    channel.session_kind = "collab"
    channel.collab_kind = kind
    channel.max_participants = max_participants
    channel.collab_started_at = now_iso
    await _update_channel_json(redis, channel)
    _log.info(
        "collab_session_created",
        short_slug=channel.short_slug,
        max_participants=max_participants,
        kind=kind,
    )
    return channel, raw_secret


async def _update_channel_json(redis: Redis, channel: ChannelData) -> None:
    """Overwrite the stored channel JSON under both slugs, preserving TTL."""
    key_short = f"file-sharing:channel:{channel.short_slug}"
    key_long = f"file-sharing:channel:{channel.long_slug}"
    payload = json.dumps(channel.to_dict())
    async with redis.pipeline(transaction=True) as pipe:
        pipe.set(key_short, payload, keepttl=True)
        pipe.set(key_long, payload, keepttl=True)
        await pipe.execute()


async def mint_invite_token(redis: Redis, slug: str, secret: str) -> str | None:
    """Mint an invite token for a Collab session.

    Refuses to mint for non-collab channels so a mis-routed slug can't
    silently cross chambers (same invariant as Screen / Watch / Call).
    """
    channel_repo = ChannelRepository(redis)
    channel = await channel_repo.fetch_channel(slug)
    if channel is None:
        return None
    if channel.session_kind != "collab":
        return None
    if not hmac.compare_digest(channel.secret, _hash_secret(secret)):
        return None
    ttl = await redis.ttl(f"file-sharing:channel:{channel.short_slug}")
    if ttl <= 0:
        return None
    raw_token = secrets.token_urlsafe(_INVITE_TOKEN_BYTES)
    await InviteTokenRepository(redis).add_invite(channel.short_slug, raw_token, ttl)
    return raw_token


async def validate_invite_token(redis: Redis, slug: str, token: str) -> bool:
    """Called from the ``("collab", "guest")`` signaling auth validator."""
    return await InviteTokenRepository(redis).validate(slug, token)


async def get_public_view(redis: Redis, slug: str) -> dict[str, object] | None:
    channel = await ChannelRepository(redis).fetch_channel(slug)
    if channel is None or channel.session_kind != "collab":
        return None
    return {
        "short_slug": channel.short_slug,
        "title": channel.title,
        "max_participants": channel.max_participants,
        "kind": channel.collab_kind,
        "started_at": channel.collab_started_at,
        "host_connected": channel.collab_started_at is not None,
    }


async def close_collab_session(redis: Redis, slug: str, secret: str) -> bool:
    channel_repo = ChannelRepository(redis)
    channel = await channel_repo.fetch_channel(slug)
    if channel is None or channel.session_kind != "collab":
        return False
    if not hmac.compare_digest(channel.secret, _hash_secret(secret)):
        return False
    await InviteTokenRepository(redis).revoke_all(channel.short_slug)
    await channel_repo.delete_channel(channel)
    from rapidly.sharing.file_sharing.signaling import signaling_manager

    await signaling_manager.close_room(channel.short_slug)
    _log.info("collab_session_closed", short_slug=channel.short_slug)
    return True


def is_enabled() -> bool:
    return settings.FILE_SHARING_COLLAB_ENABLED


def session_expires_at() -> str:
    return (datetime.now(UTC) + timedelta(seconds=COLLAB_SESSION_TTL)).isoformat()
