"""Business logic for the Screen chamber.

Plain async functions following Rapidly's module conventions. No classes,
no singletons. Each function takes the dependencies it needs (Redis
handle, channel repo, invite repo) so call sites stay testable.
"""

from __future__ import annotations

import hmac
import secrets
from datetime import UTC, datetime

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

# Invite tokens are URL-safe strings. 32 bytes → ~43-char string which
# gives >255 bits of entropy — comfortably more than the channel secret.
_INVITE_TOKEN_BYTES = 32

# Session TTL for screen. Matches file-sharing's default channel TTL; a
# host can renew via the existing renew_channel endpoint if we expose it
# later. For v1 a screen session lives up to 1 hour.
SCREEN_SESSION_TTL = 3600


# ── Session creation ──


async def create_screen_session(
    redis: Redis,
    *,
    title: str | None,
    max_viewers: int,
    user_id: str | None = None,
) -> tuple[ChannelData, str]:
    """Create a new screen-sharing session.

    Reuses :class:`ChannelRepository.create_channel` so slug generation,
    TTL management, pending-token semantics, and destruction flows work
    identically to file-sharing. Sets ``session_kind="screen"`` and the
    screen-specific fields so ``from_dict`` round-trips correctly.

    Returns ``(channel, raw_secret)``. The raw secret is never persisted —
    only its hash goes into Redis.
    """
    repo = ChannelRepository(redis)
    now_iso = datetime.now(UTC).isoformat()
    channel, raw_secret = await repo.create_channel(
        max_downloads=0,
        ttl=SCREEN_SESSION_TTL,
        title=title,
        user_id=user_id,
    )
    # Promote the channel to a screen session after creation. The
    # ChannelRepository doesn't expose session_kind yet (scope deferral —
    # adding the kwarg would be PR 5b), so we write a second SET with the
    # upgraded JSON. Because channel create uses SETEX the TTL is
    # preserved on overwrite with SET XX.
    channel.session_kind = "screen"
    channel.max_viewers = max_viewers
    channel.screen_started_at = now_iso
    await _update_channel_json(redis, channel)
    _log.info(
        "screen_session_created",
        short_slug=channel.short_slug,
        max_viewers=max_viewers,
    )
    return channel, raw_secret


async def _update_channel_json(redis: Redis, channel: ChannelData) -> None:
    """Overwrite the stored channel JSON under both slugs, preserving TTL."""
    import json

    key_short = f"file-sharing:channel:{channel.short_slug}"
    key_long = f"file-sharing:channel:{channel.long_slug}"
    payload = json.dumps(channel.to_dict())
    # KEEPTTL preserves the existing TTL set by create_channel.
    # Falls back to a manual EXPIRE pipeline if the Redis version is old
    # enough to not support KEEPTTL — but Redis >= 7 does, which is what
    # the project targets.
    async with redis.pipeline(transaction=True) as pipe:
        pipe.set(key_short, payload, keepttl=True)
        pipe.set(key_long, payload, keepttl=True)
        await pipe.execute()


# ── Invite tokens ──


async def mint_invite_token(redis: Redis, slug: str, secret: str) -> str | None:
    """Mint a one-time-use-ish invite token for a screen session.

    Requires the channel secret so only the host can issue invites.
    Returns the raw token on success, or ``None`` if the secret is wrong
    or the session doesn't exist. The token is not consumed on validation
    — guests may reconnect with the same invite during the session; the
    max_viewers cap handles fairness.
    """
    channel_repo = ChannelRepository(redis)
    channel = await channel_repo.fetch_channel(slug)
    if channel is None:
        return None
    if channel.session_kind != "screen":
        return None
    if not hmac.compare_digest(channel.secret, _hash_secret(secret)):
        return None
    # TTL of the invite SET matches the channel's remaining TTL so we
    # never leak invites past session lifetime.
    ttl = await redis.ttl(f"file-sharing:channel:{channel.short_slug}")
    if ttl <= 0:
        return None
    raw_token = secrets.token_urlsafe(_INVITE_TOKEN_BYTES)
    await InviteTokenRepository(redis).add_invite(channel.short_slug, raw_token, ttl)
    return raw_token


async def validate_invite_token(redis: Redis, slug: str, token: str) -> bool:
    """Return True if ``token`` is registered as an invite for ``slug``.

    Called from the ``("screen", "guest")`` signaling auth validator.
    """
    return await InviteTokenRepository(redis).validate(slug, token)


# ── Public view ──


async def get_public_view(redis: Redis, slug: str) -> dict[str, object] | None:
    """Return guest-facing session metadata — no secrets, no invites."""
    channel = await ChannelRepository(redis).fetch_channel(slug)
    if channel is None or channel.session_kind != "screen":
        return None
    return {
        "short_slug": channel.short_slug,
        "title": channel.title,
        "max_viewers": channel.max_viewers,
        "started_at": channel.screen_started_at,
        # Until we have cross-worker host detection, expose presence only
        # when the host's slug entry exists in Redis signaling. For v1
        # we report True if screen_started_at was set within the session
        # lifetime (best-effort; the UI uses this as a "ready to join"
        # indicator, not as a strict gate).
        "host_connected": channel.screen_started_at is not None,
    }


# ── Close ──


async def close_screen_session(redis: Redis, slug: str, secret: str) -> bool:
    """Tear down a screen session by its host secret.

    Deletes the channel, revokes every outstanding invite, and closes the
    signaling room so any connected guest is disconnected. Returns True
    on success, False if the secret doesn't match or the session is gone.
    """
    channel_repo = ChannelRepository(redis)
    channel = await channel_repo.fetch_channel(slug)
    if channel is None or channel.session_kind != "screen":
        return False
    if not hmac.compare_digest(channel.secret, _hash_secret(secret)):
        return False
    await InviteTokenRepository(redis).revoke_all(channel.short_slug)
    await channel_repo.delete_channel(channel)
    # Close the signaling room to evict live guests.
    from rapidly.sharing.file_sharing.signaling import signaling_manager

    await signaling_manager.close_room(channel.short_slug)
    _log.info(
        "screen_session_closed",
        short_slug=channel.short_slug,
    )
    return True


# ── Enablement helper ──


def is_enabled() -> bool:
    """Convenience guard used by API and signaling entry points."""
    return settings.FILE_SHARING_SCREEN_ENABLED
