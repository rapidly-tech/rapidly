"""Tests for the Redis-backed RoomTransport (PR 4c).

Uses fakeredis to exercise the single-transport paths: register/peer_exists/
host_id_for/send_to_peer/close_room behaviour against Redis state, and the
subscriber-task dispatch logic via direct invocation.

**Not covered here:** fakeredis does not route pub/sub between separate
``PubSub`` objects sharing one server (verified empirically). True
cross-worker end-to-end delivery is validated during the staging rollout
documented in specs/redis-signaling-transport.md.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, cast

import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis

from rapidly.sharing.file_sharing.signaling import Peer
from rapidly.sharing.file_sharing.signaling_redis_transport import (
    RedisRoomTransport,
)
from rapidly.sharing.file_sharing.signaling_transport import RegisterResult


class _MockWs:
    """WebSocket stand-in recording every send call."""

    def __init__(self) -> None:
        self.text_sends: list[str] = []
        self.byte_sends: list[bytes] = []
        self.close_code: int | None = None
        self.close_reason: str = ""

    async def send_text(self, data: str) -> None:
        self.text_sends.append(data)

    async def send_bytes(self, data: bytes) -> None:
        self.byte_sends.append(data)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.close_code = code
        self.close_reason = reason


@pytest_asyncio.fixture
async def transport() -> AsyncIterator[RedisRoomTransport]:
    """A RedisRoomTransport backed by a fresh fakeredis server.

    Single fakeredis instance for both the hash/string client and the
    pub/sub client; all tests that need binary roundtrip exercise the
    dispatch path directly rather than relying on fakeredis to route
    pub/sub between PubSub objects (which it doesn't reliably do).
    """
    server = FakeAsyncRedis()
    t = RedisRoomTransport(
        redis_factory=lambda: server,
        pubsub_client_factory=lambda: server,
        worker_id="worker-A",
    )
    await t.start()
    try:
        yield t
    finally:
        await t.stop()


@pytest.mark.asyncio
class TestRegisterPeer:
    async def test_first_host_gets_ok(self, transport: RedisRoomTransport) -> None:
        ws = _MockWs()
        peer = Peer(peer_id="h1", ws=ws, role="host")  # type: ignore[arg-type]
        assert await transport.register_peer("room-1", peer) is RegisterResult.OK
        assert await transport.host_id_for("room-1") == "h1"
        assert await transport.peer_exists("room-1", "h1") is True

    async def test_second_host_fails(self, transport: RedisRoomTransport) -> None:
        p1 = Peer(peer_id="h1", ws=_MockWs(), role="host")  # type: ignore[arg-type]
        p2 = Peer(peer_id="h2", ws=_MockWs(), role="host")  # type: ignore[arg-type]
        assert await transport.register_peer("room-1", p1) is RegisterResult.OK
        assert await transport.register_peer("room-1", p2) is RegisterResult.HOST_TAKEN
        assert await transport.host_id_for("room-1") == "h1"
        assert await transport.peer_exists("room-1", "h2") is False

    async def test_guest_registration_is_ok(
        self, transport: RedisRoomTransport
    ) -> None:
        host = Peer(peer_id="h1", ws=_MockWs(), role="host")  # type: ignore[arg-type]
        guest = Peer(peer_id="g1", ws=_MockWs(), role="guest")  # type: ignore[arg-type]
        assert await transport.register_peer("room-1", host) is RegisterResult.OK
        assert await transport.register_peer("room-1", guest) is RegisterResult.OK
        assert await transport.host_id_for("room-1") == "h1"
        assert await transport.peer_exists("room-1", "g1") is True


@pytest.mark.asyncio
class TestPeerExistsAndHost:
    async def test_peer_exists_false_for_unknown(
        self, transport: RedisRoomTransport
    ) -> None:
        assert await transport.peer_exists("no-room", "no-peer") is False

    async def test_host_id_for_none_when_no_host(
        self, transport: RedisRoomTransport
    ) -> None:
        # Register only a guest — no host set.
        # Note: first peer is a guest, so it occupies a slot but the host
        # key remains unset.
        g = Peer(peer_id="g1", ws=_MockWs(), role="guest")  # type: ignore[arg-type]
        assert await transport.register_peer("r", g) is RegisterResult.OK
        assert await transport.host_id_for("r") is None


@pytest.mark.asyncio
class TestSendToPeerLocal:
    """Fast path: target peer is owned by the same transport instance."""

    async def test_delivers_json_locally_without_pubsub(
        self, transport: RedisRoomTransport
    ) -> None:
        ws = _MockWs()
        peer = Peer(peer_id="p", ws=ws, role="host")  # type: ignore[arg-type]
        await transport.register_peer("r", peer)
        delivered = await transport.send_to_peer("r", "p", {"type": "offer"})
        assert delivered is True
        assert len(ws.text_sends) == 1
        assert '"offer"' in ws.text_sends[0]

    async def test_delivers_binary_locally(self, transport: RedisRoomTransport) -> None:
        ws = _MockWs()
        peer = Peer(peer_id="p", ws=ws, role="host")  # type: ignore[arg-type]
        await transport.register_peer("r", peer)
        payload = b"\x00\xff\x01\x02"
        delivered = await transport.send_to_peer("r", "p", payload)
        assert delivered is True
        assert ws.byte_sends == [payload]

    async def test_returns_false_for_unknown_peer(
        self, transport: RedisRoomTransport
    ) -> None:
        assert await transport.send_to_peer("r", "ghost", {"t": "x"}) is False


@pytest.mark.asyncio
class TestSendPublishesWhenPeerIsRemote:
    """send_to_peer must PUBLISH when the target isn't local.

    True cross-worker end-to-end delivery can't be covered in unit tests
    because fakeredis does not route pub/sub between separate PubSub
    objects sharing the same server (verified empirically). The contract
    we CAN verify here is: when the target peer isn't in ``_local_ws``
    but IS in the Redis hash, ``send_to_peer`` calls ``PUBLISH`` on the
    correct channel with the correct envelope. Real end-to-end delivery
    is validated during the staging rollout documented in
    specs/redis-signaling-transport.md.
    """

    async def test_text_message_publishes_text_envelope(
        self, transport: RedisRoomTransport
    ) -> None:
        # Register a peer in Redis but NOT in this transport's _local_ws
        # — simulates a peer owned by another worker.
        assert transport._redis is not None
        await transport._redis.hset(
            "file-sharing:p2p:room:r:peers",
            "remote-peer",
            '{"role":"guest","worker_id":"other"}',
        )
        captured: dict[str, bytes] = {}
        original_publish = transport._redis.publish

        async def fake_publish(channel: str, message: bytes | str) -> int:
            captured["channel"] = (
                channel.encode() if isinstance(channel, str) else bytes(channel)
            )
            captured["message"] = (
                message if isinstance(message, bytes) else message.encode()
            )
            return await original_publish(channel, message)

        transport._redis.publish = fake_publish

        delivered = await transport.send_to_peer("r", "remote-peer", {"type": "offer"})
        assert delivered is True
        assert captured["channel"] == b"file-sharing:p2p:peer:remote-peer"
        # Envelope: 1-byte "T" + JSON body.
        assert captured["message"][:1] == b"T"
        assert b'"offer"' in captured["message"][1:]

    async def test_binary_message_publishes_binary_envelope(
        self, transport: RedisRoomTransport
    ) -> None:
        assert transport._redis is not None
        await transport._redis.hset(
            "file-sharing:p2p:room:r:peers",
            "remote-peer",
            '{"role":"guest","worker_id":"other"}',
        )
        captured: dict[str, bytes] = {}

        async def fake_publish(channel: str, message: bytes | str) -> int:
            captured["message"] = (
                message if isinstance(message, bytes) else message.encode()
            )
            return 0

        transport._redis.publish = fake_publish

        payload = b"\x00\x01\xff"
        assert await transport.send_to_peer("r", "remote-peer", payload) is True
        assert captured["message"][:1] == b"B"
        assert captured["message"][1:] == payload


@pytest.mark.asyncio
class TestDispatchPubsubMessage:
    """The subscriber task receives an envelope and delivers to the local peer.

    Exercises the receive path directly by calling the private dispatcher,
    which is how a real pub/sub message would ultimately arrive.
    """

    async def test_text_envelope_is_delivered_as_send_text(
        self, transport: RedisRoomTransport
    ) -> None:
        ws = _MockWs()
        transport._local_ws["p"] = cast(Any, ws)  # simulate ownership
        msg = {
            "type": "message",
            "channel": b"file-sharing:p2p:peer:p",
            "data": b"T" + b'{"type":"offer"}',
        }
        await transport._dispatch_pubsub_message(msg)
        assert ws.text_sends == ['{"type":"offer"}']

    async def test_binary_envelope_is_delivered_as_send_bytes(
        self, transport: RedisRoomTransport
    ) -> None:
        ws = _MockWs()
        transport._local_ws["p"] = cast(Any, ws)
        payload = b"\x00\xff\x02"
        msg = {
            "type": "message",
            "channel": b"file-sharing:p2p:peer:p",
            "data": b"B" + payload,
        }
        await transport._dispatch_pubsub_message(msg)
        assert ws.byte_sends == [payload]

    async def test_close_envelope_invokes_ws_close_with_code(
        self, transport: RedisRoomTransport
    ) -> None:
        ws = _MockWs()
        transport._local_ws["p"] = cast(Any, ws)
        # 4010 = 0x0FAA, reason "gone"
        msg = {
            "type": "message",
            "channel": b"file-sharing:p2p:peer:p",
            "data": b"C" + b"\x0f\xaa" + b"gone",
        }
        await transport._dispatch_pubsub_message(msg)
        assert ws.close_code == 4010
        assert ws.close_reason == "gone"

    async def test_unknown_peer_is_dropped_silently(
        self, transport: RedisRoomTransport
    ) -> None:
        # No peer registered at all; dispatch must not raise.
        msg = {
            "type": "message",
            "channel": b"file-sharing:p2p:peer:never-seen",
            "data": b"T" + b'{"x":1}',
        }
        await transport._dispatch_pubsub_message(msg)  # no raise

    async def test_malformed_envelope_is_dropped_silently(
        self, transport: RedisRoomTransport
    ) -> None:
        ws = _MockWs()
        transport._local_ws["p"] = cast(Any, ws)
        # Empty data — no envelope tag
        msg = {
            "type": "message",
            "channel": b"file-sharing:p2p:peer:p",
            "data": b"",
        }
        await transport._dispatch_pubsub_message(msg)
        assert ws.text_sends == []
        assert ws.byte_sends == []


@pytest.mark.asyncio
class TestCloseRoomRemovesRedisState:
    """close_room removes the Redis hash + host string.

    Cross-worker close propagation is a staging concern (same fakeredis
    pub/sub limitation as above). We verify the Redis state transition
    here and the envelope encoding via the dispatch tests above.
    """

    async def test_removes_keys_and_returns_true(
        self, transport: RedisRoomTransport
    ) -> None:
        host = Peer(peer_id="h", ws=_MockWs(), role="host")  # type: ignore[arg-type]
        await transport.register_peer("r", host)
        assert await transport.peer_exists("r", "h") is True
        assert await transport.close_room("r") is True
        assert await transport.peer_exists("r", "h") is False
        assert await transport.host_id_for("r") is None

    async def test_returns_false_for_unknown_room(
        self, transport: RedisRoomTransport
    ) -> None:
        assert await transport.close_room("never-existed") is False


@pytest.mark.asyncio
class TestStartStopIdempotency:
    async def test_double_start_is_safe(self) -> None:
        server = FakeAsyncRedis()
        t = RedisRoomTransport(
            redis_factory=lambda: server, pubsub_client_factory=lambda: server
        )
        await t.start()
        await t.start()  # must not raise
        await t.stop()

    async def test_double_stop_is_safe(self) -> None:
        server = FakeAsyncRedis()
        t = RedisRoomTransport(
            redis_factory=lambda: server, pubsub_client_factory=lambda: server
        )
        await t.start()
        await t.stop()
        await t.stop()  # must not raise
