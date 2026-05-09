"""Tests for Call chamber's ``InviteTokenRepository`` — the Redis SET
that backs call invite-token validation.

Mirrors the collab + screen + watch chamber tests. The only intended
difference is the Redis key prefix (``file-sharing:call:invite:``).
"""

from __future__ import annotations

import hashlib

import pytest

from rapidly.redis import Redis
from rapidly.sharing.call.queries import InviteTokenRepository


def _expected_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _invite_key(slug: str) -> str:
    return f"file-sharing:call:invite:{slug}"


@pytest.mark.asyncio
class TestAddInvite:
    async def test_stores_token_hash_not_raw(self, redis: Redis) -> None:
        repo = InviteTokenRepository(redis)
        await repo.add_invite("slug-1", "raw-token-abc", ttl=600)

        members = await redis.smembers(_invite_key("slug-1"))
        decoded = {m.decode() if isinstance(m, bytes) else m for m in members}

        assert "raw-token-abc" not in decoded
        assert _expected_hash("raw-token-abc") in decoded

    async def test_sets_an_expiry(self, redis: Redis) -> None:
        repo = InviteTokenRepository(redis)
        await repo.add_invite("slug-1", "token", ttl=600)
        ttl = await redis.ttl(_invite_key("slug-1"))
        assert 0 < ttl <= 600

    async def test_multiple_adds_accumulate_in_the_set(self, redis: Redis) -> None:
        repo = InviteTokenRepository(redis)
        await repo.add_invite("slug-1", "token-a", ttl=600)
        await repo.add_invite("slug-1", "token-b", ttl=600)
        await repo.add_invite("slug-1", "token-c", ttl=600)

        count = await redis.scard(_invite_key("slug-1"))
        assert count == 3

    async def test_duplicate_raw_token_does_not_double_store(
        self, redis: Redis
    ) -> None:
        repo = InviteTokenRepository(redis)
        await repo.add_invite("slug-1", "same-token", ttl=600)
        await repo.add_invite("slug-1", "same-token", ttl=600)
        count = await redis.scard(_invite_key("slug-1"))
        assert count == 1


@pytest.mark.asyncio
class TestValidate:
    async def test_accepts_a_previously_added_token(self, redis: Redis) -> None:
        repo = InviteTokenRepository(redis)
        await repo.add_invite("slug-1", "the-token", ttl=600)
        assert await repo.validate("slug-1", "the-token") is True

    async def test_rejects_a_never_added_token(self, redis: Redis) -> None:
        repo = InviteTokenRepository(redis)
        await repo.add_invite("slug-1", "token-a", ttl=600)
        assert await repo.validate("slug-1", "token-b") is False

    async def test_rejects_an_empty_token(self, redis: Redis) -> None:
        repo = InviteTokenRepository(redis)
        await repo.add_invite("slug-1", "", ttl=600)
        assert await repo.validate("slug-1", "") is False

    async def test_is_scoped_by_slug(self, redis: Redis) -> None:
        repo = InviteTokenRepository(redis)
        await repo.add_invite("slug-a", "token", ttl=600)
        assert await repo.validate("slug-b", "token") is False

    async def test_returns_false_for_nonexistent_slug(self, redis: Redis) -> None:
        repo = InviteTokenRepository(redis)
        assert await repo.validate("never-created", "anything") is False


@pytest.mark.asyncio
class TestRevokeAll:
    async def test_drops_the_entire_set(self, redis: Redis) -> None:
        repo = InviteTokenRepository(redis)
        await repo.add_invite("slug-1", "token-a", ttl=600)
        await repo.add_invite("slug-1", "token-b", ttl=600)

        await repo.revoke_all("slug-1")

        assert await repo.validate("slug-1", "token-a") is False
        assert await repo.validate("slug-1", "token-b") is False
        assert await redis.exists(_invite_key("slug-1")) == 0

    async def test_is_idempotent(self, redis: Redis) -> None:
        repo = InviteTokenRepository(redis)
        await repo.revoke_all("fresh")
        await repo.revoke_all("fresh")

    async def test_scoped_by_slug_does_not_touch_siblings(self, redis: Redis) -> None:
        repo = InviteTokenRepository(redis)
        await repo.add_invite("slug-a", "token-a", ttl=600)
        await repo.add_invite("slug-b", "token-b", ttl=600)

        await repo.revoke_all("slug-a")

        assert await repo.validate("slug-a", "token-a") is False
        assert await repo.validate("slug-b", "token-b") is True
