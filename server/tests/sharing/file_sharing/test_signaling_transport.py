"""Tests for the RoomTransport abstraction and in-memory implementation (PR 4a).

SignalingManager is the sole implementation right now. These tests pin the
contract described in specs/room-transport-abstraction.md so PR 4b can add
a Redis-backed implementation that satisfies the same contract.
"""

from __future__ import annotations

from typing import Any

import pytest

from rapidly.sharing.file_sharing.signaling import Peer, SignalingManager
from rapidly.sharing.file_sharing.signaling_transport import RoomTransport


class _MockWs:
    """Minimal WebSocket stand-in that records every send."""

    def __init__(self) -> None:
        self.text_sends: list[str] = []
        self.byte_sends: list[bytes] = []
        self.closed: bool = False
        self.fail_sends: bool = False

    async def send_text(self, data: str) -> None:
        if self.fail_sends:
            raise RuntimeError("simulated send failure")
        self.text_sends.append(data)

    async def send_bytes(self, data: bytes) -> None:
        if self.fail_sends:
            raise RuntimeError("simulated send failure")
        self.byte_sends.append(data)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = True


def _make_manager_with_peer(
    slug: str = "room-1", role: str = "host"
) -> tuple[SignalingManager, Peer, _MockWs]:
    mgr = SignalingManager()
    room = mgr.get_or_create_room(slug)
    assert room is not None
    ws = _MockWs()
    peer = Peer(peer_id="peer-a", ws=ws, role=role)  # type: ignore[arg-type]
    room.peers[peer.peer_id] = peer
    if role == "host":
        room.host_id = peer.peer_id
    return mgr, peer, ws


class TestRoomTransportProtocolSatisfied:
    """SignalingManager must structurally satisfy the RoomTransport Protocol.

    Protocols aren't runtime-checkable by default, but @runtime_checkable on
    RoomTransport means isinstance() works (method presence only — no
    signature-level checking).
    """

    def test_signaling_manager_is_a_room_transport(self) -> None:
        mgr = SignalingManager()
        assert isinstance(mgr, RoomTransport)


@pytest.mark.asyncio
class TestSendToPeer:
    """Contract: dict → send_text, bytes → send_bytes, unknown target → False."""

    async def test_delivers_dict_as_json(self) -> None:
        mgr, _peer, ws = _make_manager_with_peer()
        delivered = await mgr.send_to_peer("room-1", "peer-a", {"type": "offer"})
        assert delivered is True
        assert len(ws.text_sends) == 1
        # Sent as JSON, not Python repr.
        assert '"type"' in ws.text_sends[0]
        assert '"offer"' in ws.text_sends[0]
        assert ws.byte_sends == []

    async def test_delivers_bytes_raw(self) -> None:
        mgr, _peer, ws = _make_manager_with_peer()
        payload = b"\x00\x01\x02\xff"
        delivered = await mgr.send_to_peer("room-1", "peer-a", payload)
        assert delivered is True
        assert ws.byte_sends == [payload]
        assert ws.text_sends == []

    async def test_returns_false_for_unknown_room(self) -> None:
        mgr = SignalingManager()
        delivered = await mgr.send_to_peer("nonexistent", "anyone", {"k": "v"})
        assert delivered is False

    async def test_returns_false_for_unknown_peer(self) -> None:
        mgr, _peer, ws = _make_manager_with_peer()
        delivered = await mgr.send_to_peer("room-1", "ghost-peer", {"k": "v"})
        assert delivered is False
        assert ws.text_sends == []  # existing peer was not written to

    async def test_swallows_websocket_errors(self) -> None:
        """A failing send must NOT raise into the caller.

        The handler-layer exception handling already deals with dead
        WebSockets at a higher level; transport-layer send failures are
        logged-and-ignored so one broken peer doesn't tear down unrelated
        code paths.
        """
        mgr, _peer, ws = _make_manager_with_peer()
        ws.fail_sends = True
        # Must still return True — the send was attempted against a
        # known-present peer. False is reserved for "target not found".
        delivered = await mgr.send_to_peer("room-1", "peer-a", {"type": "offer"})
        assert delivered is True


@pytest.mark.asyncio
class TestBroadcastPeerLeft:
    """broadcast_peer_left notifies every remaining peer; one failure
    doesn't prevent others from hearing about it.
    """

    async def test_notifies_remaining_peers(self) -> None:
        mgr = SignalingManager()
        room = mgr.get_or_create_room("room-1")
        assert room is not None
        ws_a, ws_b = _MockWs(), _MockWs()
        room.peers["peer-a"] = Peer(peer_id="peer-a", ws=ws_a, role="host")  # type: ignore[arg-type]
        room.peers["peer-b"] = Peer(peer_id="peer-b", ws=ws_b, role="guest")  # type: ignore[arg-type]

        await mgr.broadcast_peer_left("room-1", "peer-c")

        # Both sockets received a peer-left notification
        assert len(ws_a.text_sends) == 1
        assert len(ws_b.text_sends) == 1
        assert '"peer-left"' in ws_a.text_sends[0]
        assert '"peer-c"' in ws_a.text_sends[0]

    async def test_one_failing_peer_does_not_block_others(self) -> None:
        mgr = SignalingManager()
        room = mgr.get_or_create_room("room-1")
        assert room is not None
        ws_a, ws_b = _MockWs(), _MockWs()
        ws_a.fail_sends = True  # This peer will raise on send.
        room.peers["peer-a"] = Peer(peer_id="peer-a", ws=ws_a, role="host")  # type: ignore[arg-type]
        room.peers["peer-b"] = Peer(peer_id="peer-b", ws=ws_b, role="guest")  # type: ignore[arg-type]

        # Must not raise even though peer-a's send errors.
        await mgr.broadcast_peer_left("room-1", "peer-c")

        # peer-b still got the notification.
        assert len(ws_b.text_sends) == 1
        # peer-a recorded nothing (it raised).
        assert ws_a.text_sends == []

    async def test_missing_room_is_a_noop(self) -> None:
        mgr = SignalingManager()
        # No raise, no error.
        await mgr.broadcast_peer_left("nonexistent", "anyone")


class TestRoomLifecyclePreserved:
    """Existing room-management behaviour must still work after the refactor.

    These assertions are cheap smoke-checks that the transport methods
    (get_or_create_room, get_room, remove_room, remove_peer) keep the
    same semantics we relied on before PR 4a.
    """

    def test_create_then_get(self) -> None:
        mgr = SignalingManager()
        created = mgr.get_or_create_room("slug-1")
        assert created is not None
        assert mgr.get_room("slug-1") is created

    def test_remove_room_drops_it(self) -> None:
        mgr = SignalingManager()
        mgr.get_or_create_room("slug-1")
        mgr.remove_room("slug-1")
        assert mgr.get_room("slug-1") is None

    def test_remove_peer_clears_host_id_when_host_leaves(self) -> None:
        mgr, peer, _ws = _make_manager_with_peer(role="host")
        room_before = mgr.get_room("room-1")
        assert room_before is not None
        assert room_before.host_id == peer.peer_id

        mgr.remove_peer("room-1", peer.peer_id)

        room_after = mgr.get_room("room-1")
        assert room_after is not None
        assert room_after.host_id is None

    def test_remove_peer_preserves_host_id_when_guest_leaves(self) -> None:
        mgr, host_peer, _ws_h = _make_manager_with_peer(role="host")
        room = mgr.get_room("room-1")
        assert room is not None
        guest_ws = _MockWs()
        room.peers["guest-id"] = Peer(peer_id="guest-id", ws=guest_ws, role="guest")  # type: ignore[arg-type]

        mgr.remove_peer("room-1", "guest-id")

        room_after = mgr.get_room("room-1")
        assert room_after is not None
        assert room_after.host_id == host_peer.peer_id  # unchanged


def _unused_fixture_silencer(_x: Any) -> None:
    """Keeps pyright happy about the Any import (used in the _MockWs annotations)."""
    return None
