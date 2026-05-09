"""Redis-backed RoomTransport implementation (PR 4c).

Implements the ``RoomTransport`` protocol from ``signaling_transport.py``
using Redis hashes for room membership and per-peer pub/sub channels for
cross-worker message delivery. See ``specs/redis-signaling-transport.md``
for the design rationale, key layout, rollout plan, and scope deferrals.

The default deployment uses the in-memory ``SignalingManager``. This
backend is selected by setting ``FILE_SHARING_SIGNALING_BACKEND=redis``
in config.
"""

from __future__ import annotations

import asyncio
import json
import os
import struct
import time
import uuid
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any

import redis.asyncio as _redis_async
import structlog
from fastapi import WebSocket
from redis.exceptions import RedisError

from rapidly.config import settings

from .redis_scripts import ATOMIC_REGISTER_PEER_LUA
from .signaling_transport import RegisterResult

if TYPE_CHECKING:
    from .signaling import Peer, Room

_log = structlog.get_logger(__name__)


# ── Constants ──

# Key prefixes. Kept under "file-sharing:" for ops-prefix consistency even
# though the transport is chamber-agnostic — PR 4d can rename the namespace
# if a chamber-neutral prefix becomes valuable.
_ROOM_PEERS_KEY = "file-sharing:p2p:room:{slug}:peers"
_ROOM_HOST_KEY = "file-sharing:p2p:room:{slug}:host"
_PEER_CHANNEL_KEY = "file-sharing:p2p:peer:{peer_id}"

# Matches MAX_CONNECTION_LIFETIME in signaling.py; re-declared here so this
# module doesn't cross-import and create a cycle.
_ROOM_TTL_SECONDS = 6 * 60 * 60

# Matches MAX_PEERS_PER_ROOM in signaling.py; duplicated for the same reason.
_MAX_PEERS_PER_ROOM = 50

# Pub/sub envelope type bytes.
_ENV_TEXT = b"T"
_ENV_BINARY = b"B"
_ENV_CLOSE = b"C"


# ── Helpers ──


def _peers_key(slug: str) -> str:
    return _ROOM_PEERS_KEY.format(slug=slug)


def _host_key(slug: str) -> str:
    return _ROOM_HOST_KEY.format(slug=slug)


def _peer_channel(peer_id: str) -> str:
    return _PEER_CHANNEL_KEY.format(peer_id=peer_id)


def _encode_text_envelope(payload: Mapping[str, Any]) -> bytes:
    """Envelope a JSON payload for pub/sub delivery."""
    return _ENV_TEXT + json.dumps(dict(payload)).encode("utf-8")


def _encode_binary_envelope(payload: bytes) -> bytes:
    """Envelope a raw binary payload for pub/sub delivery."""
    return _ENV_BINARY + payload


def _encode_close_envelope(code: int, reason: str) -> bytes:
    """Envelope a close directive: 2-byte code + UTF-8 reason."""
    code_bytes = struct.pack(">H", code & 0xFFFF)
    return _ENV_CLOSE + code_bytes + reason.encode("utf-8")


# ── RedisRoomTransport ──


class RedisRoomTransport:
    """Cross-worker ``RoomTransport`` backed by Redis hashes + pub/sub.

    One instance per worker process. Each peer it hosts locally occupies
    two resources: a subscription on this transport's pub/sub connection
    (so pushes from other workers land here) and an entry in
    ``_local_ws`` (so this transport can deliver them to a real socket).

    The transport starts its subscriber task lazily on first async use.
    Callers that want explicit control — tests, CLI tooling — can call
    ``await transport.start()`` and ``await transport.stop()`` directly.
    """

    def __init__(
        self,
        redis_factory: Callable[[], Any] | None = None,
        pubsub_client_factory: Callable[[], Any] | None = None,
        worker_id: str | None = None,
    ) -> None:
        # Redis client for HASH/STRING/Lua ops. Uses the app's shared pool
        # when not overridden (tests inject fakeredis directly).
        # Typed as Any because the factory may return either Redis[str]
        # (decode_responses=True) or Redis[bytes] and we don't want the
        # call-site typing to fight this distinction.
        self._redis_factory: Callable[[], Any] = redis_factory or (
            lambda: _redis_async.Redis.from_url(
                settings.redis_url, decode_responses=True
            )
        )
        # Second Redis client, decode_responses=False, owned exclusively for
        # pub/sub so we can round-trip binary relay frames without base64.
        self._pubsub_client_factory: Callable[[], Any] = pubsub_client_factory or (
            lambda: _redis_async.Redis.from_url(
                settings.redis_url, decode_responses=False
            )
        )
        self._worker_id = worker_id or f"{os.getpid()}-{uuid.uuid4().hex[:8]}"

        self._redis: Any = None  # Redis client (string-decoded)
        self._pubsub_client: Any = None  # Redis client (bytes) owning pubsub
        self._pubsub: Any = None  # redis-py PubSub, typed as Any because stubs vary
        self._subscriber_task: asyncio.Task[None] | None = None

        # Local WebSocket registry — the sockets this worker owns.
        self._local_ws: dict[str, WebSocket] = {}
        # Per-worker Room objects retained only for the rate-limit counters
        # scoped out of PR 4c. Populated on first local peer register for a
        # given slug, dropped when the last local peer for that slug leaves.
        self._local_rooms: dict[str, Room] = {}

        self._start_lock = asyncio.Lock()
        self._started: bool = False
        self._stopped: bool = False

    # ── Lifecycle ──

    async def start(self) -> None:
        """Initialise Redis clients and launch the pub/sub subscriber task.

        Safe to call multiple times; subsequent calls are no-ops. Most
        callers don't need to invoke this explicitly — every async method
        on the transport ensures it has started before doing work.
        """
        async with self._start_lock:
            if self._started:
                return
            self._redis = self._redis_factory()
            self._pubsub_client = self._pubsub_client_factory()
            self._pubsub = self._pubsub_client.pubsub()
            self._subscriber_task = asyncio.create_task(
                self._run_subscriber(),
                name=f"p2p-redis-subscriber-{self._worker_id}",
            )
            self._started = True
            _log.info(
                "RedisRoomTransport started",
                worker_id=self._worker_id,
            )

    async def stop(self) -> None:
        """Cancel the subscriber task and release Redis connections.

        Idempotent. After ``stop()`` the transport must not be used again.
        """
        if self._stopped:
            return
        self._stopped = True
        if self._subscriber_task is not None:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except (asyncio.CancelledError, Exception):
                pass

        # redis-py 4.x+ exposes ``aclose``; fall back to ``close`` for
        # older stubs/versions. Both are idempotent.
        async def _close_gracefully(target: Any, name: str) -> None:
            if target is None:
                return
            close_coro = getattr(target, "aclose", None) or getattr(
                target, "close", None
            )
            if close_coro is None:
                return
            try:
                await close_coro()
            except Exception:
                _log.debug("%s close failed during stop", name)

        await _close_gracefully(self._pubsub, "pubsub")
        await _close_gracefully(self._pubsub_client, "pubsub_client")
        await _close_gracefully(self._redis, "redis")

    async def _ensure_started(self) -> None:
        if not self._started:
            await self.start()

    # ── Subscriber loop ──

    async def _run_subscriber(self) -> None:
        """Long-running task that dispatches pub/sub messages to local sockets.

        One message corresponds to one peer (identified by channel name).
        Unknown peers and malformed envelopes are logged and dropped — we
        never raise into the asyncio.Task machinery.
        """
        assert self._pubsub is not None
        try:
            async for msg in self._pubsub.listen():
                if msg.get("type") != "message":
                    continue
                await self._dispatch_pubsub_message(msg)
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.exception("RedisRoomTransport subscriber crashed; task exiting")

    async def _dispatch_pubsub_message(self, msg: Mapping[str, Any]) -> None:
        channel_raw = msg.get("channel")
        data_raw = msg.get("data")
        if not isinstance(channel_raw, (bytes, bytearray)) or not isinstance(
            data_raw, (bytes, bytearray)
        ):
            _log.debug("Dropping pubsub message with unexpected encoding")
            return
        channel = bytes(channel_raw).decode("utf-8", errors="replace")
        # Channel is "file-sharing:p2p:peer:{peer_id}" — peer_id may contain
        # colons (it's a UUID in practice but keep the slicing robust).
        peer_id_prefix = "file-sharing:p2p:peer:"
        if not channel.startswith(peer_id_prefix):
            _log.debug("Ignoring pubsub message on unexpected channel: %s", channel)
            return
        peer_id = channel[len(peer_id_prefix) :]
        ws = self._local_ws.get(peer_id)
        if ws is None:
            # Not owned by this worker anymore; another worker will take it.
            return
        data = bytes(data_raw)
        if not data:
            return
        tag, rest = data[:1], data[1:]
        try:
            if tag == _ENV_TEXT:
                await ws.send_text(rest.decode("utf-8"))
            elif tag == _ENV_BINARY:
                await ws.send_bytes(rest)
            elif tag == _ENV_CLOSE:
                if len(rest) >= 2:
                    code = struct.unpack(">H", rest[:2])[0]
                    reason = rest[2:].decode("utf-8", errors="replace")
                else:
                    code, reason = 4010, ""
                await ws.close(code=code, reason=reason)
            else:
                _log.debug("Unknown pubsub envelope tag: %r", tag)
        except Exception:
            _log.debug("Failed to deliver pubsub message to peer %s", peer_id)

    # ── Helpers that assume started ──

    def _r(self) -> Any:
        """Return the started Redis client, asserting non-None for mypy.

        Typed as ``Any`` rather than ``Redis[str]`` because callers may
        inject fakeredis or a bytes-decoded client in tests.
        """
        assert self._redis is not None, "RedisRoomTransport not started"
        return self._redis

    # ── RoomTransport — room lifecycle ──

    def get_or_create_room(self, slug: str) -> Room | None:
        """Return a worker-local Room used only for rate-limit counters.

        Redis is the source of truth for membership; this local Room is a
        side table for the per-worker relay counters that PR 4c explicitly
        keeps per-worker (see spec).
        """
        from .signaling import Room as RoomCls

        room = self._local_rooms.get(slug)
        if room is None:
            room = RoomCls()
            self._local_rooms[slug] = room
        return room

    def get_room(self, slug: str) -> Room | None:
        return self._local_rooms.get(slug)

    def remove_room(self, slug: str) -> None:
        self._local_rooms.pop(slug, None)

    async def close_room(self, slug: str) -> bool:
        """Close the room across every worker.

        PUBLISHes a close envelope to every peer's channel; the worker
        owning each peer writes the close to its WebSocket. Deletes the
        Redis membership + host keys atomically.
        """
        await self._ensure_started()
        r = self._r()
        try:
            peer_ids_raw = await r.hkeys(_peers_key(slug))
        except RedisError:
            _log.warning("close_room: HKEYS failed for slug=%s", slug)
            return False
        peer_ids = [
            p.decode() if isinstance(p, (bytes, bytearray)) else p
            for p in peer_ids_raw or []
        ]
        if not peer_ids:
            # Nothing in Redis. If we have a local room (rate-limit only),
            # clean it up. No change on Redis to report.
            self._local_rooms.pop(slug, None)
            return False
        envelope = _encode_close_envelope(4010, "Channel reported")
        for peer_id in peer_ids:
            try:
                await r.publish(_peer_channel(peer_id), envelope)
            except RedisError:
                _log.debug("close_room: publish failed for peer %s", peer_id)
        try:
            await r.delete(_peers_key(slug), _host_key(slug))
        except RedisError:
            _log.debug("close_room: delete failed for slug=%s", slug)
        self._local_rooms.pop(slug, None)
        return True

    # ── RoomTransport — peer lifecycle ──

    async def register_peer(self, slug: str, peer: Peer) -> RegisterResult:
        """Atomically admit ``peer`` into ``slug`` via the Lua script.

        On success, subscribes this worker to the peer's channel and
        records the local WebSocket.
        """
        await self._ensure_started()
        r = self._r()
        meta = json.dumps(
            {
                "role": peer.role,
                "worker_id": self._worker_id,
                "connected_at": time.time(),
            }
        )
        try:
            result = await r.eval(
                ATOMIC_REGISTER_PEER_LUA,
                2,
                _peers_key(slug),
                _host_key(slug),
                peer.peer_id,
                peer.role,
                meta,
                str(_MAX_PEERS_PER_ROOM),
                str(_ROOM_TTL_SECONDS),
            )
        except RedisError:
            _log.warning("register_peer: Lua eval failed for slug=%s", slug)
            return RegisterResult.ROOM_LIMIT_REACHED

        result_str = (
            result.decode() if isinstance(result, (bytes, bytearray)) else str(result)
        )
        if result_str == "OK":
            # Register locally AFTER Redis accepts, so a Redis reject
            # doesn't leave a dangling subscription / WebSocket mapping.
            self._local_ws[peer.peer_id] = peer.ws
            assert self._pubsub is not None
            try:
                await self._pubsub.subscribe(_peer_channel(peer.peer_id))
            except RedisError:
                _log.warning(
                    "register_peer: pubsub subscribe failed for peer %s",
                    peer.peer_id,
                )
                # Best-effort: keep the Redis row but delivery will be broken
                # until subscribe recovers. remove_peer cleans both sides.
            # Ensure a local Room exists for rate-limit counters.
            self.get_or_create_room(slug)
            return RegisterResult.OK
        if result_str == "HOST_TAKEN":
            return RegisterResult.HOST_TAKEN
        if result_str == "ROOM_FULL":
            return RegisterResult.ROOM_FULL
        _log.warning("register_peer: unexpected Lua result: %s", result_str)
        return RegisterResult.ROOM_LIMIT_REACHED

    def remove_peer(self, slug: str, peer_id: str) -> None:
        """Drop ``peer_id`` from Redis + local state.

        Intentionally sync to match the ``RoomTransport`` protocol. The
        Redis HDEL happens inside an event loop slot — we schedule it via
        ``asyncio.create_task`` instead of awaiting, so this method stays
        sync and matches the protocol contract.
        """
        self._local_ws.pop(peer_id, None)
        # Best-effort cleanup of the local Room if it's now empty. We
        # can't cheaply check cross-worker emptiness here; the Redis TTL
        # reaps abandoned rows.
        # Schedule the async cleanup on the event loop.
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop (e.g., synchronous teardown path in tests).
            return
        loop.create_task(self._async_remove_peer(slug, peer_id))

    async def _async_remove_peer(self, slug: str, peer_id: str) -> None:
        if not self._started or self._stopped:
            return
        r = self._r()
        try:
            await r.hdel(_peers_key(slug), peer_id)
            # Clear the host string if this peer was the host.
            current_host = await r.get(_host_key(slug))
            if current_host == peer_id:
                await r.delete(_host_key(slug))
        except RedisError:
            _log.debug("async remove_peer: Redis cleanup failed")
        if self._pubsub is not None:
            try:
                await self._pubsub.unsubscribe(_peer_channel(peer_id))
            except RedisError:
                _log.debug("async remove_peer: unsubscribe failed")

    async def peer_exists(self, slug: str, peer_id: str) -> bool:
        await self._ensure_started()
        r = self._r()
        try:
            return bool(await r.hexists(_peers_key(slug), peer_id))
        except RedisError:
            # Fail closed: an error in the check is treated as "not found"
            # so we don't accidentally try to deliver to a peer we can't
            # verify. Matches the handler's existing early-return shape.
            _log.debug("peer_exists: HEXISTS failed for slug=%s", slug)
            return False

    async def host_id_for(self, slug: str) -> str | None:
        await self._ensure_started()
        r = self._r()
        try:
            value = await r.get(_host_key(slug))
        except RedisError:
            _log.debug("host_id_for: GET failed for slug=%s", slug)
            return None
        if value is None or value == "" or value == b"":
            return None
        return value if isinstance(value, str) else value.decode()

    # ── RoomTransport — messaging ──

    async def send_to_peer(
        self, slug: str, peer_id: str, payload: Mapping[str, Any] | bytes
    ) -> bool:
        """Deliver ``payload`` to ``peer_id``.

        Fast path: if the peer is owned by this worker, write directly to
        its WebSocket. Slow path: PUBLISH to the peer's channel; the
        worker that subscribed will deliver.
        """
        await self._ensure_started()
        # Fast path — local peer.
        local_ws = self._local_ws.get(peer_id)
        if local_ws is not None:
            try:
                if isinstance(payload, (bytes, bytearray, memoryview)):
                    await local_ws.send_bytes(bytes(payload))
                else:
                    await local_ws.send_text(json.dumps(dict(payload)))
            except Exception:
                _log.debug(
                    "Local delivery failed for peer %s in room %s", peer_id, slug
                )
            return True

        # Cross-worker path — PUBLISH.
        r = self._r()
        try:
            exists = bool(await r.hexists(_peers_key(slug), peer_id))
        except RedisError:
            _log.debug("send_to_peer: HEXISTS failed for slug=%s", slug)
            return False
        if not exists:
            return False
        if isinstance(payload, (bytes, bytearray, memoryview)):
            envelope = _encode_binary_envelope(bytes(payload))
        else:
            envelope = _encode_text_envelope(payload)
        try:
            await r.publish(_peer_channel(peer_id), envelope)
        except RedisError:
            _log.debug("send_to_peer: publish failed for peer %s", peer_id)
        return True

    async def broadcast_peer_left(self, slug: str, departed_id: str) -> None:
        """Tell every remaining peer in ``slug`` that ``departed_id`` left.

        Uses per-peer PUBLISH for cross-worker peers and direct local
        sends for peers owned by this worker, so the message path is
        identical in both cases from the receiver's perspective.
        """
        await self._ensure_started()
        r = self._r()
        try:
            peer_ids_raw = await r.hkeys(_peers_key(slug))
        except RedisError:
            _log.debug("broadcast_peer_left: HKEYS failed for slug=%s", slug)
            return
        peer_ids = [
            p.decode() if isinstance(p, (bytes, bytearray)) else p
            for p in peer_ids_raw or []
        ]
        if not peer_ids:
            return
        message = {"type": "peer-left", "peerId": departed_id}
        envelope = _encode_text_envelope(message)
        for peer_id in peer_ids:
            if peer_id == departed_id:
                continue
            local_ws = self._local_ws.get(peer_id)
            if local_ws is not None:
                try:
                    await local_ws.send_text(json.dumps(message))
                except Exception:
                    _log.debug("Local peer-left send failed for %s", peer_id)
                continue
            try:
                await r.publish(_peer_channel(peer_id), envelope)
            except RedisError:
                _log.debug("broadcast_peer_left: publish failed for %s", peer_id)
