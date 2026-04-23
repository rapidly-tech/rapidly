"""Tests for ``rapidly/sharing/file_sharing/redis_scripts.py``.

``ATOMIC_DOWNLOAD_INCR_LUA`` is already covered by ``test_security.py``.
This file pins the other four Lua scripts that gate security-critical
state transitions:

- ``ATOMIC_INCR_EXPIRE_LUA`` — rate-limit counter (INCR + EXPIRE only
  on first increment, avoiding orphaned unbounded counters)
- ``ATOMIC_DESTROY_CHANNEL_LUA`` — atomic delete-if-pending (return
  codes 0 / -2 / 1)
- ``ATOMIC_PENDING_DESTRUCTION_LUA`` — atomic set-pending-if-not-set
  (return codes 0 / 1 / 2)
- ``ATOMIC_REGISTER_PEER_LUA`` — room admission check: HOST_TAKEN /
  ROOM_FULL / OK
"""

from __future__ import annotations

import json

import pytest

from rapidly.redis import Redis
from rapidly.sharing.file_sharing.redis_scripts import (
    ATOMIC_DESTROY_CHANNEL_LUA,
    ATOMIC_INCR_EXPIRE_LUA,
    ATOMIC_PENDING_DESTRUCTION_LUA,
    ATOMIC_REGISTER_PEER_LUA,
)

# ── ATOMIC_INCR_EXPIRE_LUA ──


@pytest.mark.asyncio
class TestAtomicIncrExpire:
    async def test_first_call_returns_1_and_sets_ttl(self, redis: Redis) -> None:
        key = "rate:test"
        value = await redis.eval(ATOMIC_INCR_EXPIRE_LUA, 1, key, 60)
        assert int(value) == 1
        # EXPIRE was set only on the first increment — TTL must be near
        # the requested window.
        ttl = await redis.ttl(key)
        assert 0 < ttl <= 60

    async def test_subsequent_calls_increment_without_resetting_ttl(
        self, redis: Redis
    ) -> None:
        key = "rate:test"
        await redis.eval(ATOMIC_INCR_EXPIRE_LUA, 1, key, 60)
        # Change the TTL to something noticeably different; the second
        # script call must NOT reset it (second branch of the ``if`` skips
        # EXPIRE).
        await redis.expire(key, 3600)
        value = await redis.eval(ATOMIC_INCR_EXPIRE_LUA, 1, key, 60)
        assert int(value) == 2
        ttl = await redis.ttl(key)
        assert ttl > 60, "EXPIRE re-armed on non-first increment"

    async def test_counter_increments_monotonically(self, redis: Redis) -> None:
        key = "rate:seq"
        for expected in range(1, 6):
            value = await redis.eval(ATOMIC_INCR_EXPIRE_LUA, 1, key, 60)
            assert int(value) == expected


# ── ATOMIC_DESTROY_CHANNEL_LUA ──


@pytest.mark.asyncio
class TestAtomicDestroyChannel:
    async def test_returns_0_when_channel_missing(self, redis: Redis) -> None:
        channel_key = "ch:missing"
        pending_key = "ch:missing:pending"
        result = await redis.eval(
            ATOMIC_DESTROY_CHANNEL_LUA, 2, channel_key, pending_key
        )
        assert int(result) == 0

    async def test_returns_minus_2_when_no_pending_flag(self, redis: Redis) -> None:
        channel_key = "ch:x"
        pending_key = "ch:x:pending"
        await redis.set(channel_key, json.dumps({"short_slug": "x"}))
        # No pending key — destruction must be rejected.
        result = await redis.eval(
            ATOMIC_DESTROY_CHANNEL_LUA, 2, channel_key, pending_key
        )
        assert int(result) == -2
        # Channel still exists.
        assert await redis.exists(channel_key) == 1

    async def test_returns_1_and_deletes_when_pending_present(
        self, redis: Redis
    ) -> None:
        channel_key = "ch:x"
        pending_key = "ch:x:pending"
        await redis.set(channel_key, json.dumps({"short_slug": "x"}))
        await redis.set(pending_key, "dummy-info")
        result = await redis.eval(
            ATOMIC_DESTROY_CHANNEL_LUA, 2, channel_key, pending_key
        )
        assert int(result) == 1
        # Both keys gone after destruction.
        assert await redis.exists(channel_key) == 0
        assert await redis.exists(pending_key) == 0

    async def test_deletes_all_ancillary_keys_passed_through_KEYS(
        self, redis: Redis
    ) -> None:
        channel_key = "ch:y"
        pending_key = "ch:y:pending"
        ancillary_a = "ch:y:reader"
        ancillary_b = "ch:y:password"
        await redis.set(channel_key, "data")
        await redis.set(pending_key, "info")
        await redis.set(ancillary_a, "a")
        await redis.set(ancillary_b, "b")

        result = await redis.eval(
            ATOMIC_DESTROY_CHANNEL_LUA,
            4,
            channel_key,
            pending_key,
            ancillary_a,
            ancillary_b,
        )
        assert int(result) == 1
        for k in (channel_key, pending_key, ancillary_a, ancillary_b):
            assert await redis.exists(k) == 0


# ── ATOMIC_PENDING_DESTRUCTION_LUA ──


@pytest.mark.asyncio
class TestAtomicPendingDestruction:
    async def test_returns_0_when_channel_missing(self, redis: Redis) -> None:
        result = await redis.eval(
            ATOMIC_PENDING_DESTRUCTION_LUA,
            2,
            "ch:missing",
            "ch:missing:pending",
            10,
            '{"info": "x"}',
        )
        assert int(result) == 0

    async def test_sets_pending_flag_with_TTL_when_channel_exists(
        self, redis: Redis
    ) -> None:
        channel_key = "ch:x"
        pending_key = "ch:x:pending"
        await redis.set(channel_key, json.dumps({"short_slug": "x"}))
        result = await redis.eval(
            ATOMIC_PENDING_DESTRUCTION_LUA,
            2,
            channel_key,
            pending_key,
            30,
            '{"reason": "test"}',
        )
        assert int(result) == 1
        assert await redis.exists(pending_key) == 1
        ttl = await redis.ttl(pending_key)
        assert 0 < ttl <= 30

    async def test_returns_2_when_pending_already_set(self, redis: Redis) -> None:
        channel_key = "ch:x"
        pending_key = "ch:x:pending"
        await redis.set(channel_key, json.dumps({"short_slug": "x"}))
        await redis.setex(pending_key, 30, "prior-info")

        result = await redis.eval(
            ATOMIC_PENDING_DESTRUCTION_LUA,
            2,
            channel_key,
            pending_key,
            30,
            '{"new": "info"}',
        )
        assert int(result) == 2
        # The prior info must NOT be overwritten on the already-pending
        # code path.
        value = await redis.get(pending_key)
        assert value is not None
        assert (value if isinstance(value, str) else value.decode()) == "prior-info"


# ── ATOMIC_REGISTER_PEER_LUA ──


@pytest.mark.asyncio
class TestAtomicRegisterPeer:
    async def test_host_registration_succeeds_when_room_empty(
        self, redis: Redis
    ) -> None:
        result = await redis.eval(
            ATOMIC_REGISTER_PEER_LUA,
            2,
            "room:abc:peers",
            "room:abc:host",
            "peer-1",
            "host",
            '{"name": "host"}',
            8,
            60,
        )
        assert (result if isinstance(result, str) else result.decode()) == "OK"
        # Host pointer set.
        host = await redis.get("room:abc:host")
        assert host is not None
        assert (host if isinstance(host, str) else host.decode()) == "peer-1"

    async def test_second_host_registration_returns_HOST_TAKEN(
        self, redis: Redis
    ) -> None:
        args = [
            "room:abc:peers",
            "room:abc:host",
        ]
        await redis.eval(
            ATOMIC_REGISTER_PEER_LUA,
            2,
            *args,
            "peer-1",
            "host",
            '{"n": 1}',
            8,
            60,
        )
        result = await redis.eval(
            ATOMIC_REGISTER_PEER_LUA,
            2,
            *args,
            "peer-2",
            "host",
            '{"n": 2}',
            8,
            60,
        )
        assert (result if isinstance(result, str) else result.decode()) == "HOST_TAKEN"

    async def test_guest_registration_succeeds_below_cap(self, redis: Redis) -> None:
        # Seed the host first so guest isn't the only peer.
        await redis.eval(
            ATOMIC_REGISTER_PEER_LUA,
            2,
            "room:abc:peers",
            "room:abc:host",
            "peer-host",
            "host",
            "{}",
            4,
            60,
        )
        result = await redis.eval(
            ATOMIC_REGISTER_PEER_LUA,
            2,
            "room:abc:peers",
            "room:abc:host",
            "peer-guest",
            "guest",
            "{}",
            4,
            60,
        )
        assert (result if isinstance(result, str) else result.decode()) == "OK"
        assert await redis.hlen("room:abc:peers") == 2

    async def test_registration_returns_ROOM_FULL_at_cap(self, redis: Redis) -> None:
        # max_peers=2, register 2 then try a third.
        for i, role in enumerate(["host", "guest"]):
            await redis.eval(
                ATOMIC_REGISTER_PEER_LUA,
                2,
                "room:abc:peers",
                "room:abc:host",
                f"peer-{i}",
                role,
                "{}",
                2,
                60,
            )
        result = await redis.eval(
            ATOMIC_REGISTER_PEER_LUA,
            2,
            "room:abc:peers",
            "room:abc:host",
            "peer-3",
            "guest",
            "{}",
            2,
            60,
        )
        assert (result if isinstance(result, str) else result.decode()) == "ROOM_FULL"

    async def test_guests_do_not_claim_the_host_slot(self, redis: Redis) -> None:
        # A guest joining an empty room should NOT set the host key.
        result = await redis.eval(
            ATOMIC_REGISTER_PEER_LUA,
            2,
            "room:abc:peers",
            "room:abc:host",
            "peer-guest",
            "guest",
            "{}",
            8,
            60,
        )
        assert (result if isinstance(result, str) else result.decode()) == "OK"
        # Host key stays empty — the host slot remains available.
        assert await redis.exists("room:abc:host") == 0
