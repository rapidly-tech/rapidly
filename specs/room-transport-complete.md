# Spec: Complete the RoomTransport protocol

**Phase:** A, PR 4b (Redis backend lands in PR 4c)
**Status:** Draft → Implemented in this commit
**Related PRs:** PR 4a (Protocol + send methods)

## Goal

Finish abstracting the remaining cross-worker-relevant operations in `handle_signaling` onto `RoomTransport`. After this PR, the three dispatchers (`_handle_binary_relay`, `_handle_relay_control`, `_handle_webrtc_signaling`) and the main `handle_signaling` loop never touch `room.peers` or `room.host_id` directly — they always go through the transport.

**No behaviour change.** All existing error messages, WebSocket close codes, and rate-limit accounting stay bit-for-bit identical.

## Non-goals

- Still no Redis code in this PR. PR 4c adds the Redis-backed implementation.
- No feature flag yet.
- Rate-limit counters (`room.relay_bytes`, `_relay_window_*`) intentionally stay as direct `room.*` access inside `_handle_binary_relay`. These are per-worker concerns by design for PR 4b; PR 4c decides whether to move them into Redis.

## What remained coupled to `Room` after PR 4a

Inventory from `grep room.peers|room.host_id` on signaling.py after PR 4a:

| Location | Access | Action |
|---|---|---|
| `_handle_binary_relay` | `relay_target_id not in room.peers` | replace with `await transport.peer_exists(slug, id)` |
| `_handle_binary_relay` | `room.relay_bytes`, `room._relay_window_*` | **stays** — rate limit is local |
| `_handle_relay_control` | `target_id not in room.peers` | replace with `await transport.peer_exists(slug, id)` |
| `_handle_webrtc_signaling` | `target_id not in room.peers` | replace with `await transport.peer_exists(slug, id)` |
| `_handle_webrtc_signaling` | `room.host_id` (connect-request default) | replace with `await transport.host_id_for(slug)` |
| `handle_signaling` | `room.host_id is not None` check + assignment + peers dict | collapse into `transport.register_peer(slug, peer)` |

Internal accesses *inside* `SignalingManager` stay — the implementation can use whatever data structure it likes. The rule is that *external callers* go through the protocol.

## Design

### 1. Three new RoomTransport methods

```python
class RegisterResult(Enum):
    OK = "ok"
    ROOM_LIMIT_REACHED = "room_limit_reached"
    HOST_TAKEN = "host_taken"
    ROOM_FULL = "room_full"


class RoomTransport(Protocol):
    ...
    async def peer_exists(self, slug: str, peer_id: str) -> bool: ...
    async def host_id_for(self, slug: str) -> str | None: ...
    async def register_peer(self, slug: str, peer: Peer) -> RegisterResult: ...
```

### 2. `register_peer` consolidates three interleaved checks

Today `handle_signaling` does:

```python
room = signaling_manager.get_or_create_room(slug)
if room is None:
    # ROOM_LIMIT_REACHED
if peer.role == "host":
    if room.host_id is not None:
        if not room.peers: signaling_manager.remove_room(slug)
        # HOST_TAKEN
if len(room.peers) >= MAX_PEERS_PER_ROOM:
    if not room.peers: signaling_manager._rooms.pop(slug, None)
    # ROOM_FULL
if peer.role == "host":
    room.host_id = peer.peer_id
room.peers[peer.peer_id] = peer
```

These five steps are logically atomic — partial failure (host set but peer not added, or peer added but room.host_id not updated) would corrupt state. Today we rely on the single event loop serialising everything. In a Redis-backed future, they must happen in a single Lua script.

Collapsing them into `transport.register_peer(slug, peer)` today makes PR 4c a clean drop-in.

Handler becomes:

```python
match await signaling_manager.register_peer(canonical_slug, peer):
    case RegisterResult.ROOM_LIMIT_REACHED:
        await _send_error(ws, "Server room limit reached")
        await ws.close(code=4029, reason="Too many rooms")
        return
    case RegisterResult.HOST_TAKEN:
        await _send_error(ws, "Room already has a host")
        await ws.close(code=4009, reason="Host already connected")
        return
    case RegisterResult.ROOM_FULL:
        await _send_error(ws, "Room is full")
        await ws.close(code=4029, reason="Room peer limit reached")
        return
```

Error messages + close codes preserved verbatim from the inline version.

### 3. `room` parameter removed from two handlers

After this PR, `_handle_relay_control` and `_handle_webrtc_signaling` no longer need `Room` — they take `canonical_slug` only. `_handle_binary_relay` keeps `room` because rate limits remain local.

Signatures:
```python
async def _handle_binary_relay(ws, room, message, canonical_slug)  # unchanged
async def _handle_relay_control(ws, peer, msg, canonical_slug)     # no room
async def _handle_webrtc_signaling(ws, peer, msg, canonical_slug)  # no room
```

## Data-model implications

None. Wire protocol unchanged. No new Redis keys (Redis backend is PR 4c).

## Tests

1. `peer_exists` returns True for a registered peer and False for an unknown peer / unknown room.
2. `host_id_for` returns the host peer_id; None when no host; None when room doesn't exist.
3. `register_peer`:
   - First host registration → `OK`, `host_id` set.
   - Second host registration → `HOST_TAKEN`, first host retained.
   - Guest registration past `MAX_PEERS_PER_ROOM` → `ROOM_FULL`.
   - Room limit reached (via `MAX_ROOMS`) → `ROOM_LIMIT_REACHED`.
4. `register_peer` side effects:
   - Empty room created just to fail is NOT left behind.
   - Successful guest does not overwrite `host_id`.

## Risk

Low — every handler change is a 1:1 replacement of a dict lookup with an awaited method call on an object the handler already has. mypy + existing tests catch missed sites.

**Kill criterion:** any existing test fails. Revert.
