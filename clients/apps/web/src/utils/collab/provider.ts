/**
 * Collab chamber — Yjs provider over ``PeerDataConnection`` (PR 17).
 *
 * Yjs is the CRDT runtime: every participant holds a ``Y.Doc`` and
 * converges on the same state regardless of edit order. This module is
 * the thin glue that pumps Yjs updates across the existing P2P data
 * channel instead of a traditional y-websocket / y-webrtc provider.
 *
 * Wire protocol
 * -------------
 * Three message types, all binary via ``send({ t, bytes })``:
 *
 *   - ``y-sync-1``  state vector. Sent to a freshly-connected peer so
 *                   it can compute the diff we're missing.
 *   - ``y-sync-2``  update. Reply to sync-1 containing everything the
 *                   sender has that the receiver lacks. Also used for
 *                   every local edit broadcast.
 *   - ``y-awareness``  encoded ``Awareness`` update (cursors, presence).
 *
 * Why not use ``y-webrtc`` or ``y-websocket`` directly?
 * -----------------------------------------------------
 * Those providers ship their own signaling + transport. Our Phase A–D
 * work already gives us a signaling server, invite tokens, and a
 * ``PeerDataConnection`` with binary framing + fragmentation. Adding
 * another provider would double the transport footprint and defeat the
 * single-auth-registry discipline. The Yjs sync *protocol* is tiny
 * (~40 lines) — we keep that, skip the provider plumbing.
 *
 * Design — the provider is transport-agnostic
 * -------------------------------------------
 * Tests plug in a plain in-memory ``CollabTransport`` pair. Production
 * plugs in a ``PeerDataConnection``-backed transport. Either way, the
 * provider never imports the transport class directly.
 */

import {
  Awareness,
  applyAwarenessUpdate,
  encodeAwarenessUpdate,
} from 'y-protocols/awareness'
import * as Y from 'yjs'

// ── Transport port ──

/** Narrow view of what the provider needs from a single peer connection.
 *
 *  Both sides implement the same shape. Anything that can ``send`` a
 *  ``{t, bytes}`` message and surface inbound messages via ``onMessage``
 *  is a valid transport. The provider never knows whether the bytes
 *  cross a real DataChannel or a JS queue. */
export interface CollabTransport {
  /** Identifier of the remote peer — used in logs and for awareness
   *  origin tagging. Opaque to the provider. */
  readonly peerId: string
  send(msg: { t: string; bytes: Uint8Array }): Promise<void>
  /** Subscribe to inbound messages. Returns an unsubscribe callback. */
  onMessage(
    handler: (msg: { t: string; bytes: Uint8Array }) => void,
  ): () => void
}

/** Narrow runtime guard for inbound messages. Uses ``unknown`` because
 *  ``PeerDataConnection.onData`` surfaces whatever the remote sent. */
export function isCollabMessage(
  x: unknown,
): x is { t: string; bytes: Uint8Array } {
  if (!x || typeof x !== 'object') return false
  const obj = x as Record<string, unknown>
  if (typeof obj.t !== 'string') return false
  if (obj.t !== 'y-sync-1' && obj.t !== 'y-sync-2' && obj.t !== 'y-awareness') {
    return false
  }
  const bytes = obj.bytes
  return bytes instanceof Uint8Array || bytes instanceof ArrayBuffer
}

// ── Room ──

export interface CollabRoomOptions {
  /** Optional existing ``Y.Doc``. Caller may share one doc across room
   *  instances (e.g., swapping rooms without re-rendering the editor). */
  doc?: Y.Doc
  /** Opaque self-identity for awareness tagging. Must be unique per
   *  client within the room; the signaling server gives us a UUID. */
  selfPeerId: string
}

export interface CollabRoom {
  readonly doc: Y.Doc
  readonly awareness: Awareness
  /** Add a new peer transport. The provider immediately sends sync-1
   *  down it and starts listening. Safe to call mid-session. */
  addPeer(transport: CollabTransport): void
  /** Drop a peer — unsubscribes the inbound handler. Does not close the
   *  underlying transport; caller owns that. */
  removePeer(peerId: string): void
  /** Tear everything down. After ``close`` the doc is still usable but
   *  no longer broadcasts edits. */
  close(): void
}

export function createCollabRoom(opts: CollabRoomOptions): CollabRoom {
  const doc = opts.doc ?? new Y.Doc()
  const awareness = new Awareness(doc)

  // Peer registry: id → (transport, unsubscribe). Storing the
  // unsubscribe lets ``removePeer`` detach without leaking.
  const peers = new Map<
    string,
    { transport: CollabTransport; unsubscribe: () => void }
  >()

  // A locally-originated update must be broadcast; a remote-originated
  // update must NOT be re-broadcast (it came in via y-sync-2 from a
  // peer who already has it in their doc). The origin tag is the
  // inbound transport instance so the receiving branch can set it; any
  // non-tagged update is treated as local.
  //
  // Why this matters: without it, a 3-peer mesh would produce amplified
  // update storms — every peer re-sends every peer's update to every
  // other peer on each applyUpdate.
  const updateHandler = (update: Uint8Array, origin: unknown): void => {
    if (origin === 'remote') return
    const msg = { t: 'y-sync-2', bytes: update }
    for (const { transport } of peers.values()) {
      // Fire-and-forget: backpressure is handled inside PeerDataConnection.
      // Errors on one peer shouldn't block the others.
      void transport.send(msg).catch(() => {
        /* swallowed — transport layer logs its own errors */
      })
    }
  }
  doc.on('update', updateHandler)

  const awarenessHandler = (_changes: unknown, origin: unknown): void => {
    if (origin === 'remote') return
    const update = encodeAwarenessUpdate(awareness, [awareness.clientID])
    const msg = { t: 'y-awareness', bytes: update }
    for (const { transport } of peers.values()) {
      void transport.send(msg).catch(() => {
        /* swallowed */
      })
    }
  }
  awareness.on('update', awarenessHandler)

  function handleInbound(
    transport: CollabTransport,
    msg: { t: string; bytes: Uint8Array },
  ): void {
    const bytes =
      msg.bytes instanceof Uint8Array ? msg.bytes : new Uint8Array(msg.bytes)

    if (msg.t === 'y-sync-1') {
      // Peer sent us their state vector — reply with the diff they lack.
      const diff = Y.encodeStateAsUpdate(doc, bytes)
      void transport.send({ t: 'y-sync-2', bytes: diff }).catch(() => {
        /* swallowed */
      })
      return
    }

    if (msg.t === 'y-sync-2') {
      // An update — apply with ``'remote'`` origin so our update
      // handler does not re-broadcast and cause a ping-pong.
      Y.applyUpdate(doc, bytes, 'remote')
      return
    }

    if (msg.t === 'y-awareness') {
      applyAwarenessUpdate(awareness, bytes, 'remote')
      return
    }
  }

  function addPeer(transport: CollabTransport): void {
    if (peers.has(transport.peerId)) {
      // Idempotent — treat as replacement to avoid leaked subscriptions
      // when the mesh reconnects.
      removePeer(transport.peerId)
    }
    const unsubscribe = transport.onMessage((msg) =>
      handleInbound(transport, msg),
    )
    peers.set(transport.peerId, { transport, unsubscribe })
    // Sync step 1: send our state vector. Peer will reply with y-sync-2
    // containing any updates we're missing.
    const sv = Y.encodeStateVector(doc)
    void transport.send({ t: 'y-sync-1', bytes: sv }).catch(() => {
      /* swallowed — addPeer is fire-and-forget; caller doesn't await */
    })
  }

  function removePeer(peerId: string): void {
    const entry = peers.get(peerId)
    if (!entry) return
    entry.unsubscribe()
    peers.delete(peerId)
  }

  function close(): void {
    for (const { unsubscribe } of peers.values()) unsubscribe()
    peers.clear()
    doc.off('update', updateHandler)
    awareness.off('update', awarenessHandler)
    awareness.destroy()
  }

  return { doc, awareness, addPeer, removePeer, close }
}
