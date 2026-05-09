# Spec: RoomTransport abstraction (in-memory only)

**Phase:** A, PR 4a (the Redis backend lands in PR 4b)
**Status:** Draft → Implemented in this commit
**Related PRs:** PR 3 (auth registry)

## Why this is split from PR 4b

PLATFORM_PLAN.md §4 describes a single "PR 4" that introduces both the transport abstraction and the Redis backend. In practice that's a ~600-line diff with staged rollout, which violates the small-PR principle from §2.

Splitting it lets us land the abstraction safely (this PR, zero behavior change) and then layer in the Redis backend in PR 4b with a clean diff that only touches one new file.

## Goal

Introduce a `RoomTransport` Protocol that describes the operations `handle_signaling` performs on signaling room state: peer registration, room lookup, peer-to-peer message delivery.

Refactor the hot-path handlers so every cross-peer send goes through the transport rather than reaching into `room.peers[target].ws.send_*()` directly. After this PR, swapping in a Redis-backed transport (PR 4b) changes **zero lines** of `handle_signaling` or the three `_handle_*` dispatchers.

**No behavior change.** File-sharing error rates, latency, rate-limit semantics, close codes, and room lifecycle all remain bit-for-bit identical.

## Non-goals

- No Redis code in this PR.
- No feature flag — there is still only one backend.
- No change to the `Room` or `Peer` dataclasses.
- No change to rate-limit accounting. `room.relay_bytes` and the per-second window stay where they are; PR 4b decides whether to move them into Redis.

## Design

### 1. New module: `signaling_transport.py`

```python
class RoomTransport(Protocol):
    """Operations on signaling room state that may cross worker boundaries.

    The current in-memory implementation never actually crosses a boundary;
    the Protocol exists so PR 4b can introduce a Redis backend without
    touching the handlers.
    """

    def get_or_create_room(self, slug: str) -> Room | None: ...
    def get_room(self, slug: str) -> Room | None: ...
    def remove_room(self, slug: str) -> None: ...
    def remove_peer(self, slug: str, peer_id: str) -> None: ...
    async def close_room(self, slug: str) -> bool: ...
    async def send_to_peer(
        self, slug: str, peer_id: str, payload: Mapping[str, Any] | bytes
    ) -> bool: ...
    async def broadcast_peer_left(self, slug: str, departed_id: str) -> None: ...
```

### 2. `SignalingManager` now declares itself a `RoomTransport`

The class already implements every operation except `send_to_peer` and `broadcast_peer_left`. Those two methods get added and the handlers are updated to call them.

### 3. One new method: `send_to_peer`

```python
async def send_to_peer(
    self, slug: str, peer_id: str, payload: Mapping[str, Any] | bytes
) -> bool:
    """Deliver a payload to `peer_id` in room `slug`. Returns True if sent.

    In the in-memory backend this looks up the local peer and writes to its
    WebSocket. In the Redis backend (PR 4b), the same call will fan out via
    PUBSUB when the target peer is on a different worker.
    """
```

### 4. Handler refactor

Four call sites today reach into `room.peers` + a direct `ws.send_*` call:

- `_notify_peer_left` → becomes `signaling_manager.broadcast_peer_left`.
- `_handle_binary_relay` → `signaling_manager.send_to_peer(slug, target_id, payload_bytes)`.
- `_handle_relay_control` → `signaling_manager.send_to_peer(slug, target_id, relay_msg_dict)`.
- `_handle_webrtc_signaling` → `signaling_manager.send_to_peer(slug, target_id, relay_dict)`.

The handlers that previously took `(room)` now take the canonical `slug` too, because the transport will look up the peer by its `(slug, peer_id)` pair — this matches the key shape we'll need for Redis in PR 4b.

### 5. What the handlers still need `room` for

Only the local concerns stay coupled to `Room`:
- `room.host_id` for default routing when `targetId` is omitted.
- `room.relay_bytes` / `_relay_window_*` for rate-limit accounting.

These stay as direct attribute access for this PR. PR 4b decides whether to promote them into the transport interface.

## Data-model / protocol implications

None. Wire protocol unchanged. Redis key space unchanged (no new keys added in this PR).

## Tests

1. `SignalingManager` satisfies the `RoomTransport` Protocol structurally (static check via `isinstance` won't work — Protocols aren't runtime by default — so we use a static-style `cast` assertion inside the tests and rely on mypy in verify.sh).
2. `send_to_peer` delivers to a registered local peer.
3. `send_to_peer` returns `False` for an unknown peer in a known room.
4. `send_to_peer` returns `False` for an unknown room.
5. `send_to_peer` supports both `dict` (JSON-serialised) and `bytes` payloads.
6. `broadcast_peer_left` notifies every remaining peer and skips peers whose `ws.send_text` raises.

## References consulted

- **Polar upstream:** no direct analog — Polar has no WebSocket rooms. Pattern borrowed from our own `AuthValidator` registry (PR 3) where an abstraction was introduced in the same hot-path module.
- **LiveKit:** their room fanout is SFU-internal and not portable. Not a useful reference here.
- **Chamber reference:** N/A.

## Risk

Low — every handler change is "pull out a 3-line inline send into a single method call on an object you already have." TypeScript/mypy + existing tests catch any missed site.

**Kill criterion:** any existing test fails after the refactor.
