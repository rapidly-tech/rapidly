"""Redis queries for the Screen chamber.

The Screen chamber reuses ``ChannelRepository`` from
``file_sharing/queries.py`` for channel-backed state (slugs, secrets,
TTL). This module adds a thin layer for the invite-token SET that only
Screen uses.

One new Redis key prefix: ``file-sharing:screen:invite:`` (plural hashes).
Everything else goes through the file_sharing channel repo.
"""

from __future__ import annotations

import hashlib

import structlog

from rapidly.redis import Redis

_log = structlog.get_logger(__name__)


# ── Constants ──

# Invite tokens are stored as SHA-256 hashes in a Redis SET so a single
# SISMEMBER call resolves "is this token valid for this session?".
_INVITE_SET_KEY = "file-sharing:screen:invite:{slug}"


def _invite_set_key(slug: str) -> str:
    return _INVITE_SET_KEY.format(slug=slug)


def _hash_invite_token(raw_token: str) -> str:
    """Hash an invite token for storage / comparison.

    Uses SHA-256 rather than keyed BLAKE2b because invite tokens are
    non-secret from the host's perspective — the host freely hands them
    to guests. The hash is just a consistent lookup key, not a password
    hash. Matches the hash used by ``validate_invite_token``.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


# ── Repository ──


class InviteTokenRepository:
    """Tiny wrapper around the Redis SET holding per-session invite hashes."""

    def __init__(self, redis: Redis):
        self._redis = redis

    async def add_invite(self, slug: str, raw_token: str, ttl: int) -> None:
        """Register ``raw_token`` as a valid invite for ``slug``.

        TTL matches the channel's TTL so the invite set expires together
        with the session; orphaned invites never linger.
        """
        key = _invite_set_key(slug)
        token_hash = _hash_invite_token(raw_token)
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.sadd(key, token_hash)
            pipe.expire(key, ttl)
            await pipe.execute()

    async def validate(self, slug: str, raw_token: str) -> bool:
        """Return True if ``raw_token`` is a registered invite for ``slug``."""
        if not raw_token:
            return False
        token_hash = _hash_invite_token(raw_token)
        return bool(await self._redis.sismember(_invite_set_key(slug), token_hash))

    async def revoke_all(self, slug: str) -> None:
        """Delete every invite for ``slug``. Called by close_screen_session."""
        await self._redis.delete(_invite_set_key(slug))
