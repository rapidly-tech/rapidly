"""WebSocket signaling server for P2P file sharing.

Replaces the third-party PeerJS signaling server (0.peerjs.com) with
a self-hosted WebSocket endpoint. The server only relays SDP offers/answers
and ICE candidates between peers — it never sees file content.

Room model: each channel slug maps to one room. One uploader (validated
by channel secret) and multiple downloaders (validated by reader token).

DEPLOYMENT CONSTRAINT — SINGLE WORKER REQUIRED
===============================================
Signaling rooms are stored **in-memory** (``_rooms`` dict), NOT in Redis.
This means peers on different worker processes cannot see each other's rooms,
and file transfers will silently fail.

You **must** run the signaling endpoint with exactly one worker process::

    uvicorn rapidly.app:app --workers 1
    # or: gunicorn -w 1 -k uvicorn.workers.UvicornWorker rapidly.app:app

If multiple workers are detected at runtime, ``check_single_worker()`` will:
- **Development**: log an error (once per worker lifetime)
- **Production**: raise ``RuntimeError`` to prevent silent failures

To scale horizontally, either:
1. Use **sticky sessions** (e.g. Nginx ``ip_hash``) to pin clients to one worker
2. Replace in-memory rooms with **Redis pub/sub** (not yet implemented)
3. Deploy the signaling endpoint on a **separate single-worker service**
"""

import asyncio
import hmac
import json
import os
import time
import uuid
from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass, field
from typing import Any

import structlog
from fastapi import WebSocket, WebSocketDisconnect
from redis import RedisError

from rapidly.redis import Redis

from . import actions as file_sharing_service
from .queries import ChannelData, ChannelRepository, _hash_secret
from .redis_scripts import ATOMIC_INCR_EXPIRE_LUA
from .utils import hash_ip

_log = structlog.get_logger(__name__)


# ── Constants and Limits ──

# Auth must arrive within this many seconds of connection
AUTH_TIMEOUT_SECONDS = 10

# Maximum size of a single signaling message (64KB — generous for SDP + ICE)
MAX_SIGNALING_MESSAGE_SIZE = 64 * 1024

# Room/connection caps to prevent unbounded memory growth (DoS protection)
MAX_ROOMS = 10_000
MAX_PEERS_PER_ROOM = 50

# WebSocket rate limiting: per-IP connection rate
WS_CONN_RATE_LIMIT = 20  # max connections per window
WS_CONN_RATE_WINDOW = 60  # seconds

# WebSocket rate limiting: per-connection message rate
WS_MSG_RATE_LIMIT = 60  # max messages per window
WS_MSG_RATE_WINDOW = 10  # seconds

# Maximum connection lifetime (prevents zombie connections from leaking rooms)
MAX_CONNECTION_LIFETIME = 6 * 60 * 60  # 6 hours

# Relay limits
MAX_RELAY_SESSION_BYTES = 10 * 1024 * 1024 * 1024  # 10 GB per channel
RELAY_RATE_LIMIT_BYTES_PER_SEC = 50 * 1024 * 1024  # 50 MB/s

# Stale empty room threshold — rooms with no peers for this long are garbage collected
STALE_ROOM_SECONDS = 15 * 60  # 15 minutes

# Throttle stale room cleanup to avoid O(n) scan on every connection
_CLEANUP_INTERVAL = 60  # seconds


# ── Data Models ──


@dataclass
class Peer:
    """A connected peer in a signaling room."""

    peer_id: str
    ws: WebSocket
    role: str  # canonical "host" or "guest"; "uploader"/"downloader" are accepted
    # at auth time as aliases and normalized to the canonical forms.
    relay_mode: bool = False  # True when peer has switched to relay mode


@dataclass
class Room:
    """A signaling room for one channel."""

    peers: dict[str, Peer] = field(default_factory=dict)
    host_id: str | None = None  # canonical name; previously uploader_id.
    created_at: float = field(default_factory=time.monotonic)
    last_emptied_at: float = field(default_factory=time.monotonic)
    relay_bytes: int = 0  # Total bytes relayed for this room
    # Per-second relay rate tracking (sliding window)
    _relay_window_start: float = 0.0
    _relay_window_bytes: int = 0


# ── Channel Management ──


class SignalingManager:
    """Manages in-memory signaling rooms for P2P connections.

    Encapsulates room state that was previously in module-level globals,
    improving testability and preventing accidental cross-contamination.

    Requires a single worker process — see ``check_single_worker()``.
    """

    def __init__(self) -> None:
        self._rooms: dict[str, Room] = {}
        self._multi_worker_warned = False
        self._multi_worker_detected = False
        self._last_cleanup_time: float = 0.0

    async def check_single_worker(self, redis: Redis) -> None:
        """Detect multi-worker deployments and warn once.

        Signaling rooms are in-memory, so peers on different workers can't
        see each other.  Registers the current PID in a Redis set and logs
        an error if multiple PIDs are active.

        Stale PIDs from reloaded processes (``--reload``) are pruned before
        the check to avoid false positives during development.
        """
        if self._multi_worker_warned:
            return

        key = "file-sharing:signaling-workers"
        pid = str(os.getpid())
        try:
            await redis.sadd(key, pid)
            await redis.expire(key, 300)  # auto-cleanup after 5 min

            members = await redis.smembers(key)

            # Prune PIDs from dead processes (e.g. after --reload restart)
            stale_pids = []
            for m in members:
                m_str = m if isinstance(m, str) else m.decode()
                if m_str == pid:
                    continue
                try:
                    os.kill(int(m_str), 0)  # signal 0 = existence check
                except (OSError, ValueError):
                    stale_pids.append(m)
            if stale_pids:
                await redis.srem(key, *stale_pids)
                members = members - set(stale_pids)
        except RedisError:
            # Fail-open: skip multi-worker check during transient Redis issues
            # (matches _check_ws_connection_rate pattern)
            return

        if len(members) > 1:
            self._multi_worker_warned = True
            self._multi_worker_detected = True

            from rapidly.config import settings

            msg = (
                "Multiple worker processes detected for signaling (%s). "
                "In-memory signaling rooms require a single worker (--workers 1). "
                "Peers on different workers will NOT be able to connect. "
                "Use sticky sessions or switch to Redis pub/sub."
            )
            if settings.is_production():
                raise RuntimeError(msg % members)
            _log.error(msg, worker_pids=members)

    def get_or_create_room(self, slug: str) -> Room | None:
        """Get or create a room, enforcing global room cap.

        Returns None if the global room limit is reached and the slug
        doesn't already have a room.
        """
        now = time.monotonic()
        if now - self._last_cleanup_time > _CLEANUP_INTERVAL:
            self._last_cleanup_time = now
            self._cleanup_stale_rooms()
        if slug not in self._rooms:
            if len(self._rooms) >= MAX_ROOMS:
                return None
            self._rooms[slug] = Room()
        return self._rooms[slug]

    def _cleanup_stale_rooms(self) -> None:
        """Remove empty rooms that have been idle beyond STALE_ROOM_SECONDS."""
        now = time.monotonic()
        stale = [
            slug
            for slug, room in self._rooms.items()
            if not room.peers and (now - room.last_emptied_at) > STALE_ROOM_SECONDS
        ]
        for slug in stale:
            self._rooms.pop(slug, None)
        if stale:
            _log.debug("Cleaned up %d stale empty rooms", len(stale))

    def get_room(self, slug: str) -> Room | None:
        """Get a room by slug, or None if it doesn't exist."""
        return self._rooms.get(slug)

    def remove_room(self, slug: str) -> None:
        """Remove a room by slug if it exists."""
        self._rooms.pop(slug, None)

    @property
    def multi_worker_detected(self) -> bool:
        return self._multi_worker_detected

    def remove_peer(self, slug: str, peer_id: str) -> None:
        room = self._rooms.get(slug)
        if not room:
            return
        room.peers.pop(peer_id, None)
        if room.host_id == peer_id:
            room.host_id = None
        if not room.peers:
            room.last_emptied_at = time.monotonic()

    async def close_room(self, slug: str) -> bool:
        """Close a signaling room, disconnecting all peers.

        Used by the report endpoint to stop new connections to a reported channel.
        Returns True if a room was found and closed.
        """
        room = self._rooms.pop(slug, None)
        if room is None:
            return False
        for peer in list(room.peers.values()):
            try:
                await peer.ws.close(code=4010, reason="Channel reported")
            except Exception:
                _log.debug("Failed to close peer %s during room close", peer.peer_id)
        return True


# Singleton instance
signaling_manager = SignalingManager()


# ── Rate Limiting ──


async def _check_ws_connection_rate(redis: Redis, client_ip: str) -> bool:
    """Check per-IP WebSocket connection rate. Returns True if allowed.

    Fails **closed** on Redis errors — rejects the connection rather than
    allowing unmetered traffic during outages. Consistent with the HTTP
    rate limiter's fail-closed approach.
    """
    ip_hash = hash_ip(client_ip)
    key = f"file-sharing:ws-rate:conn:{ip_hash}"
    try:
        current = await redis.eval(ATOMIC_INCR_EXPIRE_LUA, 1, key, WS_CONN_RATE_WINDOW)
    except RedisError:
        _log.warning("WebSocket rate limit check failed — rejecting (fail-closed)")
        return False
    return int(current) <= WS_CONN_RATE_LIMIT


# ── Signal Helpers ──


async def close_room(slug: str) -> bool:
    """Module-level convenience for ``signaling_manager.close_room``.

    Preserves the existing import used by ``service.py``.
    """
    return await signaling_manager.close_room(slug)


async def _notify_peer_left(room: Room, departed_id: str) -> None:
    """Tell remaining peers that one disconnected."""
    msg = json.dumps({"type": "peer-left", "peerId": departed_id})
    for peer in list(room.peers.values()):
        try:
            await peer.ws.send_text(msg)
        except Exception:
            _log.debug(
                "Failed to notify peer %s of departure %s",
                peer.peer_id,
                departed_id,
            )


async def _send_json(ws: WebSocket, data: dict[str, Any]) -> None:
    await ws.send_text(json.dumps(data))


async def _send_error(ws: WebSocket, message: str) -> None:
    await _send_json(ws, {"type": "error", "message": message})


# ── Authentication ──

# Canonical role names on the wire. "uploader" / "downloader" are accepted
# as aliases for one release window and normalized before any downstream
# code touches them. New session kinds should only ever emit "host" / "guest".
ROLE_ALIASES: dict[str, str] = {"uploader": "host", "downloader": "guest"}
CANONICAL_ROLES: frozenset[str] = frozenset({"host", "guest"})


@dataclass
class AuthContext:
    """Arguments passed to every auth validator.

    Bundling into a dataclass (rather than long positional signatures) means
    future session kinds can add their own helpers without forcing every
    existing validator to grow matching parameters.
    """

    ws: WebSocket
    slug: str
    role: str  # canonical "host" or "guest"
    channel: ChannelData
    msg: dict[str, Any]  # the auth message body
    repo: ChannelRepository
    client_ip: str


AuthValidator = Callable[[AuthContext], Awaitable[bool]]

# Registry keyed by (session_kind, role). File-sharing registers its two
# validators below; future chambers (screen, watch, ...) register their own
# via @register_auth_validator decorators on module import.
_AUTH_VALIDATORS: dict[tuple[str, str], AuthValidator] = {}


def register_auth_validator(
    session_kind: str, role: str
) -> Callable[[AuthValidator], AuthValidator]:
    """Register a WebSocket auth validator for a (session_kind, role) pair.

    Fails loudly at import time on duplicate registration so we never silently
    shadow an existing validator.

    The validator itself is responsible for sending the specific error message
    and closing the WebSocket before returning False; this preserves the
    existing error-semantics (e.g. "Payment required" vs generic
    "Authentication failed") that downstream UIs already depend on.
    """
    if role not in CANONICAL_ROLES:
        raise RuntimeError(
            f"register_auth_validator: role must be canonical ({CANONICAL_ROLES}), "
            f"got {role!r}"
        )

    def decorator(fn: AuthValidator) -> AuthValidator:
        key = (session_kind, role)
        if key in _AUTH_VALIDATORS:
            raise RuntimeError(f"Duplicate auth validator registration for {key}")
        _AUTH_VALIDATORS[key] = fn
        return fn

    return decorator


# ── File-sharing auth validators ──
#
# Verbatim extractions of the inline logic that previously lived in
# _authenticate(). Behaviour is bit-for-bit identical — error strings and
# WebSocket close codes are preserved so any client relying on them keeps
# working across the deploy.


@register_auth_validator("file", "host")
async def _validate_file_host(ctx: AuthContext) -> bool:
    """Host (uploader) of a file channel authenticates with the channel secret."""
    secret = ctx.msg.get("secret", "")
    if not secret or not hmac.compare_digest(ctx.channel.secret, _hash_secret(secret)):
        await _send_error(ctx.ws, "Authentication failed")
        await ctx.ws.close(code=4003, reason="Forbidden")
        return False
    return True


@register_auth_validator("file", "guest")
async def _validate_file_guest(ctx: AuthContext) -> bool:
    """Guest (downloader) of a file channel — reader token + optional payment."""
    # Reader token: required if one is stored OR if a token is still pending
    # registration (uploader hasn't yet set it).
    token = ctx.msg.get("token", "")
    if token:
        valid = await ctx.repo.validate_reader_token(
            ctx.slug, token, channel=ctx.channel
        )
        if not valid:
            await _send_error(ctx.ws, "Authentication failed")
            await ctx.ws.close(code=4003, reason="Forbidden")
            return False
    else:
        if await ctx.repo.has_reader_token(
            ctx.slug, channel=ctx.channel
        ) or await ctx.repo.is_pending_token(ctx.slug, channel=ctx.channel):
            await _send_error(ctx.ws, "Authentication failed")
            await ctx.ws.close(code=4003, reason="Forbidden")
            return False

    # Payment gate: paid channels require a valid payment token.
    # Accept from the auth message OR an httpOnly cookie (preferred).
    if ctx.channel.is_paid:
        from .queries import _decrypt_token

        raw_cookie = ctx.ws.cookies.get("rapidly_pt", "")
        try:
            decrypted_cookie = _decrypt_token(raw_cookie) if raw_cookie else ""
        except Exception:
            decrypted_cookie = ""
        payment_token = ctx.msg.get("paymentToken", "") or decrypted_cookie
        buyer_fingerprint = hash_ip(ctx.client_ip)
        if not payment_token or not await ctx.repo.validate_payment_token(
            ctx.slug,
            payment_token,
            channel=ctx.channel,
            buyer_fingerprint=buyer_fingerprint,
        ):
            await _send_error(ctx.ws, "Payment required")
            await ctx.ws.close(code=4003, reason="Payment required")
            return False

    return True


async def _authenticate(
    ws: WebSocket, slug: str, redis: Redis, *, client_ip: str = "unknown"
) -> tuple[Peer, str] | None:
    """Wait for an auth message and validate credentials.

    Returns a (Peer, canonical_slug) tuple on success, or None after
    sending an error and closing. The canonical slug is always the
    channel's short_slug, ensuring both short and long slug connections
    end up in the same room.
    """
    try:
        raw = await asyncio.wait_for(ws.receive_text(), timeout=AUTH_TIMEOUT_SECONDS)
    except TimeoutError:
        await _send_error(ws, "Auth timeout")
        await ws.close(code=4008, reason="Auth timeout")
        return None
    except WebSocketDisconnect:
        return None

    # Enforce size limit on auth message (same as relay loop)
    if len(raw) > MAX_SIGNALING_MESSAGE_SIZE:
        await _send_error(ws, "Auth message too large")
        await ws.close(code=4001, reason="Message too large")
        return None

    try:
        msg = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        await _send_error(ws, "Invalid JSON")
        await ws.close(code=4001, reason="Invalid auth message")
        return None

    if msg.get("type") != "auth":
        await _send_error(ws, "First message must be auth")
        await ws.close(code=4001, reason="Expected auth message")
        return None

    # Normalize role: accept legacy "uploader"/"downloader" as aliases for
    # "host"/"guest" during the deprecation window. New chambers only emit
    # the canonical forms.
    raw_role = msg.get("role")
    role = ROLE_ALIASES.get(raw_role, raw_role) if isinstance(raw_role, str) else None
    if role not in CANONICAL_ROLES:
        await _send_error(ws, "Invalid role")
        await ws.close(code=4001, reason="Invalid role")
        return None

    repo = ChannelRepository(redis)
    channel = await repo.fetch_channel(slug)
    if channel is None:
        # Generic error to prevent channel enumeration
        await _send_error(ws, "Authentication failed")
        await ws.close(code=4003, reason="Forbidden")
        return None

    # Dispatch to the validator for this (session_kind, role) pair. If no
    # validator is registered we fail closed with a generic error — never
    # leak which axis is wrong.
    validator = _AUTH_VALIDATORS.get((channel.session_kind, role))
    if validator is None:
        await _send_error(ws, "Authentication failed")
        await ws.close(code=4003, reason="Forbidden")
        return None

    ctx = AuthContext(
        ws=ws,
        slug=slug,
        role=role,
        channel=channel,
        msg=msg,
        repo=repo,
        client_ip=client_ip,
    )
    if not await validator(ctx):
        # Validator has already sent its specific error + close code.
        return None

    peer_id = str(uuid.uuid4())
    return (Peer(peer_id=peer_id, ws=ws, role=role), channel.short_slug)


# ── WebSocket Handling ──


async def _handle_binary_relay(
    ws: WebSocket, room: Room, message: MutableMapping[str, Any]
) -> bool | None:
    """Handle a binary relay frame (relay:chunk).

    Returns True to continue the loop, None to close the connection
    (relay limit exceeded), or False if the message is not a binary frame.
    """
    if not (message.get("type") == "websocket.receive" and message.get("bytes")):
        return False

    binary_data = message["bytes"]
    if len(binary_data) < 4:
        return True
    # Parse relay frame: [4-byte header len][header JSON][binary payload]
    header_len = int.from_bytes(binary_data[:4], "big")
    if header_len > MAX_SIGNALING_MESSAGE_SIZE or header_len > len(binary_data) - 4:
        return True
    try:
        relay_header = json.loads(binary_data[4 : 4 + header_len])
    except (json.JSONDecodeError, TypeError):
        return True
    if relay_header.get("type") != "relay:chunk":
        return True
    relay_target_id = relay_header.get("targetId")
    if not relay_target_id:
        return True
    target = room.peers.get(relay_target_id)
    if not target:
        return True
    # Rate limit and size cap — check before incrementing to prevent bypass
    binary_payload = binary_data[4 + header_len :]
    payload_len = len(binary_payload)
    if room.relay_bytes + payload_len > MAX_RELAY_SESSION_BYTES:
        await _send_error(ws, "Relay session size limit exceeded")
        await ws.close(code=4029, reason="Relay limit exceeded")
        return None
    # Per-second throughput rate limit
    now = time.monotonic()
    if now - room._relay_window_start >= 1.0:
        room._relay_window_start = now
        room._relay_window_bytes = 0
    if room._relay_window_bytes + payload_len > RELAY_RATE_LIMIT_BYTES_PER_SEC:
        await _send_error(ws, "Relay rate limit exceeded")
        await ws.close(code=4029, reason="Relay rate limit exceeded")
        return None
    room._relay_window_bytes += payload_len
    room.relay_bytes += payload_len
    # Forward binary frame directly to target
    try:
        await target.ws.send_bytes(binary_payload)
    except Exception:
        _log.debug("Failed to relay binary to %s", relay_target_id)
    return True


async def _handle_relay_control(
    ws: WebSocket, peer: Peer, room: Room, msg: dict[str, Any], canonical_slug: str
) -> bool:
    """Handle relay control messages (relay:start/ack/done/data).

    Returns True if the message was handled, False otherwise.
    """
    msg_type = msg.get("type")
    if msg_type not in ("relay:start", "relay:ack", "relay:done", "relay:data"):
        return False

    target_id = msg.get("targetId")
    if not target_id:
        await _send_error(ws, "Missing targetId for relay")
        return True
    target = room.peers.get(target_id)
    if not target:
        await _send_error(ws, "Relay target not found")
        return True

    if msg_type == "relay:start":
        peer.relay_mode = True
        _log.info(
            "Relay started: %s -> %s in room %s",
            peer.peer_id,
            target_id,
            canonical_slug,
        )

    # Forward relay control messages
    relay_msg: dict[str, Any] = {
        "type": msg_type,
        "fromId": peer.peer_id,
    }
    if msg_type == "relay:data" and "data" in msg:
        data_val = msg["data"]
        if isinstance(data_val, str) and len(data_val) <= MAX_SIGNALING_MESSAGE_SIZE:
            relay_msg["data"] = data_val
    await _send_json(target.ws, relay_msg)
    return True


async def _handle_webrtc_signaling(
    ws: WebSocket, peer: Peer, room: Room, msg: dict[str, Any]
) -> bool:
    """Handle WebRTC signaling messages (offer/answer/ice-candidate/connect-request).

    Validates fields, builds an allowlisted relay payload, and forwards to the
    target peer. Returns True if the message was handled, False otherwise.
    """
    msg_type = msg.get("type")
    if msg_type not in ("offer", "answer", "ice-candidate", "connect-request"):
        return False

    target_id = msg.get("targetId")
    if not target_id:
        # For connect-request from guest, route to the room's host.
        if msg_type == "connect-request" and room.host_id:
            target_id = room.host_id
        else:
            await _send_error(ws, "Missing targetId")
            return True

    target = room.peers.get(target_id)
    if not target:
        await _send_error(ws, "Target peer not found")
        return True

    # Forward with sender's ID — allowlist known fields only
    # to prevent injection of arbitrary data.
    # Type-check each field to prevent malformed values from
    # being relayed to the target peer.
    relay: dict[str, Any] = {
        "type": msg_type,
        "fromId": peer.peer_id,
    }
    # String-only fields
    for field_name in ("sdp", "candidate"):
        if field_name in msg:
            val = msg[field_name]
            if isinstance(val, str) and len(val) <= MAX_SIGNALING_MESSAGE_SIZE:
                relay[field_name] = val
    # Nullable string fields (per WebRTC spec: sdpMid and
    # usernameFragment can be null)
    for field_name in ("sdpMid", "usernameFragment"):
        if field_name in msg:
            val = msg[field_name]
            if val is None or (isinstance(val, str) and len(val) <= 255):
                relay[field_name] = val
    # Nullable int field
    if "sdpMLineIndex" in msg:
        val = msg["sdpMLineIndex"]
        if val is None or isinstance(val, int):
            relay["sdpMLineIndex"] = val
    # Relay metadata only from the host (role-based restriction)
    # with size cap (4KB) and flat-dict validation to prevent abuse
    if "metadata" in msg and peer.role == "host":
        meta = msg["metadata"]
        if isinstance(meta, dict) and all(
            isinstance(k, str) and isinstance(v, (str, int, float, bool, type(None)))
            for k, v in meta.items()
        ):
            meta_str = json.dumps(meta)
            if len(meta_str) <= 4096:
                relay["metadata"] = meta
    await _send_json(target.ws, relay)
    return True


async def handle_signaling(ws: WebSocket, slug: str, redis: Redis) -> None:
    """Main signaling loop for one WebSocket connection."""
    # Warn/error if multiple worker processes are serving signaling
    await signaling_manager.check_single_worker(redis)

    # Reject connections when multiple workers detected — signaling won't work
    if signaling_manager.multi_worker_detected:
        await _send_error(
            ws,
            "Signaling unavailable: multiple worker processes detected. "
            "Deploy with --workers 1.",
        )
        await ws.close(
            code=4503,
            reason="Signaling requires single worker process",
        )
        return

    # Per-IP connection rate limit
    client_ip = ws.client.host if ws.client else "unknown"
    if not await _check_ws_connection_rate(redis, client_ip):
        await _send_error(ws, "Too many connections")
        await ws.close(code=4029, reason="Rate limit exceeded")
        return

    auth_result = await _authenticate(ws, slug, redis, client_ip=client_ip)
    if auth_result is None:
        return
    peer, canonical_slug = auth_result

    room = signaling_manager.get_or_create_room(canonical_slug)
    if room is None:
        await _send_error(ws, "Server room limit reached")
        await ws.close(code=4029, reason="Too many rooms")
        return

    # Enforce one host per room.
    if peer.role == "host":
        if room.host_id is not None:
            await _send_error(ws, "Room already has a host")
            await ws.close(code=4009, reason="Host already connected")
            # Clean up empty room if we just created it
            if not room.peers:
                signaling_manager.remove_room(canonical_slug)
            return

    # Enforce per-room peer cap (prevents single-room DoS)
    if len(room.peers) >= MAX_PEERS_PER_ROOM:
        await _send_error(ws, "Room is full")
        await ws.close(code=4029, reason="Room peer limit reached")
        # Clean up empty room if we just created it
        if not room.peers:
            signaling_manager._rooms.pop(canonical_slug, None)
        return

    # Set host_id AFTER the peer cap check to avoid orphaning it on early return.
    if peer.role == "host":
        room.host_id = peer.peer_id

    room.peers[peer.peer_id] = peer

    # From here, all exits go through the finally block for cleanup
    msg_count = 0
    window_start = time.monotonic()
    try:
        # Send welcome with peer ID and ICE servers
        ice_config = await file_sharing_service.build_ice_config()
        ice_servers_list = [
            {
                "urls": s.urls,
                **({"username": s.username} if s.username else {}),
                **({"credential": s.credential} if s.credential else {}),
            }
            for s in ice_config.ice_servers
        ]

        await _send_json(
            ws,
            {
                "type": "welcome",
                "peerId": peer.peer_id,
                "iceServers": ice_servers_list,
            },
        )

        # Relay loop with per-connection message rate limiting
        # Connection lifetime is bounded by MAX_CONNECTION_LIFETIME
        # to prevent zombie connections from leaking rooms.
        connection_deadline = time.monotonic() + MAX_CONNECTION_LIFETIME
        while True:
            remaining = connection_deadline - time.monotonic()
            if remaining <= 0:
                await _send_error(ws, "Connection lifetime exceeded")
                await ws.close(code=4008, reason="Connection lifetime exceeded")
                return
            try:
                message = await asyncio.wait_for(
                    ws.receive(), timeout=min(remaining, 300)
                )
            except TimeoutError:
                # 5-minute receive timeout — check if lifetime exceeded
                continue

            # Handle binary relay frames
            binary_result = await _handle_binary_relay(ws, room, message)
            if binary_result is True:
                continue
            if binary_result is None:
                return  # relay limit exceeded, connection closed

            # Extract text data
            raw = message.get("text", "")
            if not raw:
                continue

            # Per-connection message rate throttle
            now = time.monotonic()
            if now - window_start >= WS_MSG_RATE_WINDOW:
                msg_count = 0
                window_start = now
            msg_count += 1
            if msg_count > WS_MSG_RATE_LIMIT:
                await _send_error(ws, "Message rate limit exceeded")
                await ws.close(code=4029, reason="Rate limit exceeded")
                return

            # Reject oversized messages to prevent memory abuse
            if len(raw) > MAX_SIGNALING_MESSAGE_SIZE:
                await _send_error(ws, "Message too large")
                continue

            try:
                msg = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                await _send_error(ws, "Invalid JSON")
                continue

            # Dispatch to message type handlers
            if await _handle_relay_control(ws, peer, room, msg, canonical_slug):
                continue
            if await _handle_webrtc_signaling(ws, peer, room, msg):
                continue
            await _send_error(ws, "Unknown message type")
    except WebSocketDisconnect:
        pass
    except Exception:
        _log.exception(
            "Unexpected error in signaling relay for slug=%s peer=%s",
            canonical_slug,
            peer.peer_id,
        )
    finally:
        signaling_manager.remove_peer(canonical_slug, peer.peer_id)
        room_after = signaling_manager.get_room(canonical_slug)
        if room_after:
            await _notify_peer_left(room_after, peer.peer_id)
