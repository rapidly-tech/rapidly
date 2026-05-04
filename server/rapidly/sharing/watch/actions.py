"""Business logic for the Watch chamber.

Plain async functions following the Rapidly module convention. Same
shape as ``sharing/screen/actions.py`` — deliberately so that the two
chambers can diverge only where they must.
"""

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


# ── Constants ──

_INVITE_TOKEN_BYTES = 32

# Default session TTL. Watch sessions can be long — a movie is ~2h —
# but v1 matches Screen at 1h. Hosts can recreate for longer material.
WATCH_SESSION_TTL = 3600


# ── Session creation ──


async def create_watch_session(
    redis: Redis,
    *,
    title: str | None,
    max_viewers: int,
    source_url: str | None,
    source_kind: str = "url",
    user_id: str | None = None,
) -> tuple[ChannelData, str]:
    """Create a new watch-together session.

    Reuses ``ChannelRepository.create_channel`` so slug generation, TTL
    management, and destruction flows work identically to file-sharing.
    Sets ``session_kind="watch"`` and the watch-specific fields so
    ``from_dict`` round-trips correctly.
    """
    repo = ChannelRepository(redis)
    now_iso = datetime.now(UTC).isoformat()
    channel, raw_secret = await repo.create_channel(
        max_downloads=0,
        ttl=WATCH_SESSION_TTL,
        title=title,
        user_id=user_id,
    )
    channel.session_kind = "watch"
    channel.max_viewers = max_viewers
    channel.watch_source_url = source_url
    channel.watch_source_kind = source_kind
    channel.watch_started_at = now_iso
    await _update_channel_json(redis, channel)
    _log.info(
        "watch_session_created",
        short_slug=channel.short_slug,
        max_viewers=max_viewers,
        source_kind=source_kind,
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


# ── Invite tokens ──


async def mint_invite_token(redis: Redis, slug: str, secret: str) -> str | None:
    """Mint an invite token for a watch session.

    Requires the channel secret. Refuses to mint for non-watch channels
    so a mis-routed slug can't silently cross chambers.
    """
    channel_repo = ChannelRepository(redis)
    channel = await channel_repo.fetch_channel(slug)
    if channel is None:
        return None
    if channel.session_kind != "watch":
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
    """Called from the ``("watch", "guest")`` signaling auth validator."""
    return await InviteTokenRepository(redis).validate(slug, token)


# ── Public view ──


async def get_public_view(redis: Redis, slug: str) -> dict[str, object] | None:
    channel = await ChannelRepository(redis).fetch_channel(slug)
    if channel is None or channel.session_kind != "watch":
        return None
    return {
        "short_slug": channel.short_slug,
        "title": channel.title,
        "max_viewers": channel.max_viewers,
        "source_url": channel.watch_source_url,
        "source_kind": channel.watch_source_kind,
        "started_at": channel.watch_started_at,
        "host_connected": channel.watch_started_at is not None,
    }


# ── Close ──


async def close_watch_session(redis: Redis, slug: str, secret: str) -> bool:
    channel_repo = ChannelRepository(redis)
    channel = await channel_repo.fetch_channel(slug)
    if channel is None or channel.session_kind != "watch":
        return False
    if not hmac.compare_digest(channel.secret, _hash_secret(secret)):
        return False
    await InviteTokenRepository(redis).revoke_all(channel.short_slug)
    await channel_repo.delete_channel(channel)
    from rapidly.sharing.file_sharing.signaling import signaling_manager

    await signaling_manager.close_room(channel.short_slug)
    _log.info("watch_session_closed", short_slug=channel.short_slug)
    return True


# ── Enablement helper ──


def is_enabled() -> bool:
    return settings.FILE_SHARING_WATCH_ENABLED


# ── Helpers re-exported for API layer ──


def session_expires_at() -> str:
    return (datetime.now(UTC) + timedelta(seconds=WATCH_SESSION_TTL)).isoformat()
