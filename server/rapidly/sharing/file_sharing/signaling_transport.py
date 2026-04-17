"""RoomTransport abstraction for P2P signaling.

Describes the operations ``handle_signaling`` performs on signaling room
state: peer registration, room lookup, peer-to-peer message delivery.

Today there is one implementation — the in-memory ``SignalingManager`` —
which satisfies this Protocol structurally. The abstraction exists so a
Redis-backed implementation (PR 4b) can be dropped in behind a feature
flag without touching ``handle_signaling`` or any of the ``_handle_*``
dispatchers.

Everything an implementation has to do is expressed here; nothing else
in signaling.py reaches past this interface to the underlying dict or
Redis keys. That's the whole point of introducing the Protocol.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    # Avoid a circular import at module-load time: signaling.py imports this
    # module, and the types it needs (Room) live in signaling.py itself.
    from .signaling import Room


@runtime_checkable
class RoomTransport(Protocol):
    """Operations on signaling room state that may cross worker boundaries.

    The current in-memory implementation never actually crosses a boundary;
    a future Redis-backed implementation will. Consumers (``handle_signaling``
    and the three ``_handle_*`` dispatchers) must reach state only through
    methods on this interface so swapping backends is diff-free.

    ``send_to_peer`` and ``broadcast_peer_left`` are the only async methods
    because those are the ones that will eventually involve a Redis PUBLISH.
    Room lifecycle operations stay sync because in the in-memory backend
    they're fast dict operations, and in the Redis backend they'll use a
    client that we already make available without await (via a blocking
    connection pool or Lua script execution).
    """

    # ── Room lifecycle ──

    def get_or_create_room(self, slug: str) -> Room | None:
        """Return the room for ``slug``, creating it if absent.

        Returns ``None`` if the global room cap is reached.
        """
        ...

    def get_room(self, slug: str) -> Room | None:
        """Return the room for ``slug`` without creating it."""
        ...

    def remove_room(self, slug: str) -> None:
        """Drop ``slug`` from the index. No-op if not present."""
        ...

    async def close_room(self, slug: str) -> bool:
        """Close a room, disconnecting every peer. Returns True if found."""
        ...

    # ── Peer lifecycle ──

    def remove_peer(self, slug: str, peer_id: str) -> None:
        """Unregister ``peer_id`` from ``slug``.

        Updates the host-index if the departing peer was the host.
        """
        ...

    # ── Messaging ──

    async def send_to_peer(
        self, slug: str, peer_id: str, payload: Mapping[str, Any] | bytes
    ) -> bool:
        """Deliver ``payload`` to ``peer_id`` in room ``slug``.

        Returns True if the send was attempted against a reachable peer
        and False if the target is unknown (room missing or peer not in
        the room). Actual WebSocket failures (send_text raising) are
        logged and swallowed — the caller never blocks on a dead peer.

        A ``dict``-like payload is serialised as JSON; a ``bytes``
        payload is forwarded as a binary WebSocket frame. These are the
        only two shapes the signaling protocol uses today.
        """
        ...

    async def broadcast_peer_left(self, slug: str, departed_id: str) -> None:
        """Notify remaining peers in ``slug`` that ``departed_id`` left.

        Errors from individual peers are logged and swallowed — one
        unreachable peer must not block notification of the rest.
        """
        ...
