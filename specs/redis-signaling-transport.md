# Spec: Redis-backed RoomTransport + feature flag

**Phase:** A, PR 4c (completes Phase A — unblocks horizontal scaling)
**Status:** Draft → Implemented in this commit
**Related PRs:** PR 4a (Protocol), PR 4b (Protocol complete)

## Goal

Add a Redis-backed `RoomTransport` implementation alongside the in-memory one, gated by a feature flag. When enabled, peers on different worker processes can participate in the same signaling room — killing the `--workers 1` deployment constraint documented in `signaling.py`'s module docstring.

**No behaviour change in the default configuration.** `FILE_SHARING_SIGNALING_BACKEND=memory` remains the default, so every existing deployment keeps working unchanged.

## Non-goals

- Rate-limit counters (`room.relay_bytes`, `_relay_window_*`) stay **per-worker** even when backend is `redis`. Known consequence: aggregate relay cap becomes `N_workers × MAX_RELAY_SESSION_BYTES` and aggregate throughput cap becomes `N_workers × RELAY_RATE_LIMIT_BYTES_PER_SEC`. Documented as a scope deferral; PR 4d can move counters into Redis if we need fleet-wide caps.
- No changes to the wire protocol or client SDK.
- `MAX_ROOMS` global cap is **not** enforced in Redis mode. The single-worker check counted a single dict; across workers there's no cheap equivalent. 10k rooms per worker × N workers is still reasonable; TTLs + rate limits contain runaway cases.

## Key design

### 1. Redis key layout

| Key | Type | Purpose | TTL |
|---|---|---|---|
| `file-sharing:p2p:room:{slug}:peers` | hash, field=peer_id, value=JSON `{role, worker_id, connected_at}` | Source of truth for room membership across workers | `MAX_CONNECTION_LIFETIME` (6h), refreshed on register |
| `file-sharing:p2p:room:{slug}:host` | string (peer_id) | Fast lookup for `connect-request` default routing | Same TTL, kept in sync via Lua |
| `file-sharing:p2p:peer:{peer_id}` (PUBSUB channel) | — | One channel per peer; owning worker subscribes on register | — |

### 2. PUBSUB fan-out model

**One channel per peer**, not one per worker:

- When peer `P` registers on worker `W`: worker subscribes to `file-sharing:p2p:peer:P` on its shared pubsub connection.
- When any worker needs to deliver a message to `P`: `PUBLISH file-sharing:p2p:peer:P <envelope>`. The worker that subscribed receives it and writes to its local WebSocket.
- When peer `P` disconnects: unsubscribe from `peer:P`, HDEL from the peers hash.

Why per-peer channels rather than per-worker:
- No custom routing logic — the subscription topology *is* the routing table.
- Workers don't need to know each others' IDs at runtime.
- Churn cost: one `SUBSCRIBE`/`UNSUBSCRIBE` per peer session. File-sharing sessions last minutes-to-hours; this is cheap.

### 3. PUBSUB envelope format

Binary framing, no base64 overhead:

```
[1 byte: type][payload bytes]
```

| type | meaning | payload shape |
|---|---|---|
| `b"T"` | JSON text message | UTF-8 bytes of `json.dumps(msg)` |
| `b"B"` | Binary relay frame | raw bytes |
| `b"C"` | Close peer | 2-byte big-endian close code + UTF-8 reason |

Per-peer channels mean the receiver already knows the target peer_id from the channel name — no need to encode it in the envelope.

### 4. Atomic `register_peer` via Lua

The three admission checks (`HOST_TAKEN`, `ROOM_FULL`, and the write itself) must happen atomically across workers. Without Lua, two concurrent host-registrations on different workers can both succeed. Script:

```lua
-- KEYS[1] = peers hash; KEYS[2] = host string
-- ARGV[1] = peer_id; ARGV[2] = role; ARGV[3] = peer_meta JSON
-- ARGV[4] = MAX_PEERS_PER_ROOM; ARGV[5] = TTL seconds
-- Returns: "OK" | "HOST_TAKEN" | "ROOM_FULL"
```

The `OK` path writes both the peers field and (if role=="host") the host string, then `EXPIRE`s both keys in a single command sequence. `HOST_TAKEN` and `ROOM_FULL` paths make no writes so no cleanup is needed.

### 5. Subscriber task lifecycle

Each `RedisRoomTransport` owns **one** pubsub connection and **one** long-running asyncio task reading from it. When a peer registers, the worker calls `pubsub.subscribe(channel)` on that connection.

Lazy start: the transport starts its subscriber task on first async use (behind a `start_lock`). No FastAPI-lifespan wiring required. Callers that know the lifecycle (tests) can call `await transport.start()` / `await transport.stop()` explicitly.

Shutdown: `stop()` cancels the subscriber task and unsubscribes everything; safe to call repeatedly.

### 6. Local state on each worker

Even with Redis as the source of truth, each worker keeps:
- `_local_ws: dict[peer_id, WebSocket]` — the WebSockets it owns, for delivery.
- `_local_rooms: dict[slug, Room]` — kept ONLY for per-worker rate-limit counters (see non-goals). Populated lazily when a peer registers; reaped when the last local peer for a slug leaves.

No local cache of peer membership or host_id — those go straight through Redis on every check. The cost is one `HEXISTS` / `GET` per message, which is sub-millisecond on the same box.

## Factory

`signaling.py` picks the implementation at import time:

```python
if settings.FILE_SHARING_SIGNALING_BACKEND == "redis":
    signaling_manager: RoomTransport = RedisRoomTransport(
        redis_factory=get_redis,
        worker_id=str(uuid.uuid4()),
    )
else:
    signaling_manager: RoomTransport = SignalingManager()
```

`SignalingManager` is unchanged (in-memory); `RedisRoomTransport` is the new class. Every existing import of `signaling_manager` keeps working because both implement the same `RoomTransport` Protocol.

## Staged rollout

1. Ship with flag defaulted to `memory`. Zero change for every deployment.
2. Staging: flip to `redis` with `--workers 1`. Run the existing file-sharing e2e suite. Soak 48h.
3. Staging: keep `redis`, scale to `--workers 2`. Verify multi-worker peers can see each other. Soak 24h.
4. Prod: flip to `redis`, keep `--workers 1` for one release. Observation window 72h.
5. Prod: scale to `--workers 2` in one pod. Observation window 72h.
6. Prod: fleet-wide `--workers 2+`.

**Kill criterion at each step:** file-sharing error rate rises >0.1% over baseline. Flip flag back to `memory`; no code change required.

## Tests

Against `fakeredis` (already in test deps):

1. `register_peer` happy path: host then guest both get `OK`; hash and host-string populated.
2. `register_peer` `HOST_TAKEN`: second host registration fails; first retains the slot.
3. `register_peer` `ROOM_FULL`: enforced atomically.
4. `peer_exists` / `host_id_for` read straight from Redis.
5. `send_to_peer` to a peer owned by the same transport instance delivers locally without publishing.
6. `send_to_peer` to a peer owned by a different transport instance (simulated multi-worker) routes via PUBSUB.
7. `broadcast_peer_left` reaches every peer across both local and remote transports.
8. `close_room` disconnects every peer across workers.
9. Subscriber task cancellation cleans up subscriptions.

**Not in unit-test scope:** actual Redis cluster behaviour, PUBSUB failover during Redis restarts, latency under real network conditions. Those are staging-soak concerns.

## References consulted

- **Polar upstream:** no WebSocket room patterns. N/A.
- **LiveKit server-room code:** confirmed the per-room fanout pattern we're adopting is standard.
- **Redis docs:** atomic Lua scripting + pub/sub + per-key TTL semantics (all well-established).

## Risk

High — this is the hot path and multi-worker behaviour is hard to unit-test completely.

**Mitigations:**
- Default flag value = `memory` means no deployment changes by default.
- In-memory path is untouched (same class, same tests).
- Staged rollout has 6 distinct checkpoints with a revert path at each.
- Unit tests cover the cross-transport delivery case via two separate `RedisRoomTransport` instances sharing the same fakeredis.

**Kill criterion:** file-sharing error rate >0.1% over baseline at any staging or prod step. Flip `FILE_SHARING_SIGNALING_BACKEND=memory` in config. No code revert required — the code path is dormant under the memory flag.
