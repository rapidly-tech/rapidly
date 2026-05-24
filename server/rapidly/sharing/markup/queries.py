"""Redis queries for the Collab chamber.

Reuses ``ChannelRepository`` for channel-backed state; adds the invite
token SET specific to Collab. One new Redis key prefix:
``file-sharing:collab:invite:{slug}``.
"""

from __future__ import annotations

import hashlib

import structlog

from rapidly.redis import Redis

_log = structlog.get_logger(__name__)


_INVITE_SET_KEY = "file-sharing:collab:invite:{slug}"


def _invite_set_key(slug: str) -> str:
    return _INVITE_SET_KEY.format(slug=slug)


def _hash_invite_token(raw_token: str) -> str:
    """SHA-256 — same scheme Screen / Watch / Call use."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class InviteTokenRepository:
    """Tiny wrapper around the Redis SET holding per-session invite hashes."""

    def __init__(self, redis: Redis):
        self._redis = redis

    async def add_invite(self, slug: str, raw_token: str, ttl: int) -> None:
        key = _invite_set_key(slug)
        token_hash = _hash_invite_token(raw_token)
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.sadd(key, token_hash)
            pipe.expire(key, ttl)
            await pipe.execute()

    async def validate(self, slug: str, raw_token: str) -> bool:
        if not raw_token:
            return False
        token_hash = _hash_invite_token(raw_token)
        return bool(await self._redis.sismember(_invite_set_key(slug), token_hash))

    async def revoke_all(self, slug: str) -> None:
        await self._redis.delete(_invite_set_key(slug))
