/**
 * Collab chamber — Yjs provider over ``PeerDataConnection``.
 *
 * Yjs is the CRDT runtime: every participant holds a ``Y.Doc`` and
 * converges on the same state regardless of edit order. This module is
 * the thin glue that pumps Yjs updates across the existing P2P data
 * channel instead of a traditional y-websocket / y-webrtc provider.
 *
 * Wire protocol
 * -------------
 * Four message types, binary payload on the existing ``{t, ...}`` DC
 * framing:
 *
 *   - ``y-sync-hello``  capability handshake. Sent immediately on peer
 *                       add; carries ``{e: "v1" | null}`` indicating
 *                       whether this side is ready to speak E2EE. Until
 *                       both sides have sent hello, outbound traffic is
 *                       deferred so we never need to rewrite a frame
 *                       mid-flight.
 *   - ``y-sync-1``  state vector. Sent to a freshly-connected peer so
 *                   it can compute the diff we're missing.
 *   - ``y-sync-2``  update. Reply to sync-1 containing everything the
 *                   sender has that the receiver lacks. Also used for
 *                   every local edit broadcast.
 *   - ``y-awareness``  encoded ``Awareness`` update (cursors, presence).
 *
 * When E2EE is active, y-sync-1/2/awareness messages ride with an
 * extra ``iv: Uint8Array`` field; the bytes are AES-GCM ciphertext.
 * See ``specs/collab-e2ee.md``.
 *
 * Why not use ``y-webrtc`` or ``y-websocket`` directly?
 * -----------------------------------------------------
 * Those providers ship their own signaling + transport. Our Phase A–D
 * work already gives us a signaling server, invite tokens, and a
 * ``PeerDataConnection`` with binary framing + fragmentation. Adding
 * another provider would double the transport footprint and defeat the
 * single-auth-registry discipline.
 */

import {
  Awareness,
  applyAwarenessUpdate,
  encodeAwarenessUpdate,
} from 'y-protocols/awareness'
import * as Y from 'yjs'

import { decryptGcm, encryptGcm } from '@/utils/crypto/aes-gcm'
import { deriveSubKey, infoFor } from '@/utils/crypto/hkdf'

// ── Transport port ──

/** Narrow view of what the provider needs from a single peer connection.
 *
 *  Both sides implement the same shape. Anything that can ``send`` a
 *  ``{t, bytes}`` message and surface inbound messages via ``onMessage``
 *  is a valid transport. The provider never knows whether the bytes
 *  cross a real DataChannel or a JS queue. */
export interface CollabTransport {
  readonly peerId: string
  send(msg: CollabWireMessage): Promise<void>
  onMessage(handler: (msg: CollabWireMessage) => void): () => void
}

/** Every message on the wire. ``iv`` is present when the message was
 *  encrypted; absent for plaintext + for the hello handshake itself. */
export type CollabWireMessage = {
  t: string
  bytes: Uint8Array
  iv?: Uint8Array
}

const KNOWN_TYPES = new Set([
  'y-sync-hello',
  'y-sync-1',
  'y-sync-2',
  'y-awareness',
])

export function isCollabMessage(x: unknown): x is CollabWireMessage {
  if (!x || typeof x !== 'object') return false
  const obj = x as Record<string, unknown>
  if (typeof obj.t !== 'string' || !KNOWN_TYPES.has(obj.t)) return false
  const bytes = obj.bytes
  if (!(bytes instanceof Uint8Array || bytes instanceof ArrayBuffer)) {
    return false
  }
  if (obj.iv !== undefined) {
    if (!(obj.iv instanceof Uint8Array || obj.iv instanceof ArrayBuffer)) {
      return false
    }
  }
  return true
}

// ── Keys ──

/** Pair of purpose-scoped sub-keys derived from the room master. */
export interface CollabSessionKeys {
  /** Used for y-sync-1 + y-sync-2. */
  sync: CryptoKey
  /** Used for y-awareness. */
  awareness: CryptoKey
}

/** Derive the Collab sub-keys from a master + salt. Caller owns the
 *  master + salt lifecycle (distributed via URL fragment in PR C). */
export async function deriveCollabKeys(
  masterKey: CryptoKey,
  salt: Uint8Array,
): Promise<CollabSessionKeys> {
  const [sync, awareness] = await Promise.all([
    deriveSubKey(masterKey, infoFor('collab', 'sync'), salt),
    deriveSubKey(masterKey, infoFor('collab', 'awareness'), salt),
  ])
  return { sync, awareness }
}

// ── Room ──

export interface CollabRoomOptions {
  doc?: Y.Doc
  selfPeerId: string
  /** Optional sub-keys for E2EE. If omitted, the room runs in
   *  plaintext mode and the y-sync-hello handshake will advertise no
   *  E2EE capability. A peer with keys paired against one without
   *  will converge on plaintext (backward-compat rolling deploy). */
  keys?: CollabSessionKeys
}

export interface CollabRoom {
  readonly doc: Y.Doc
  readonly awareness: Awareness
  addPeer(transport: CollabTransport): void
  removePeer(peerId: string): void
  /** For test + telemetry: current e2ee state with each peer. */
  peerEncryptionStatus(peerId: string): 'pending' | 'e2ee' | 'plaintext' | null
  close(): void
}

type PeerState = {
  transport: CollabTransport
  unsubscribe: () => void
  /** Has the peer's hello arrived? */
  theirHelloReceived: boolean
  theirE2ee: boolean
  /** Has our hello gone out? (Always true after addPeer; kept for
   *  symmetry + future async-hello paths.) */
  ourHelloSent: boolean
  /** Resolved after both hellos known — determines whether subsequent
   *  traffic is encrypted or plaintext. Until resolved, sync-1 / edits
   *  are queued into ``pendingOut``. */
  settled: boolean
  useE2ee: boolean
  /** Messages queued while the handshake is in flight. */
  pendingOut: CollabWireMessage[]
}

export function createCollabRoom(opts: CollabRoomOptions): CollabRoom {
  const doc = opts.doc ?? new Y.Doc()
  const awareness = new Awareness(doc)
  const selfHasE2ee = opts.keys !== undefined

  const peers = new Map<string, PeerState>()

  async function encryptIfNeeded(
    peer: PeerState,
    t: 'y-sync-1' | 'y-sync-2' | 'y-awareness',
    plaintext: Uint8Array,
  ): Promise<CollabWireMessage> {
    if (!peer.useE2ee || !opts.keys) return { t, bytes: plaintext }
    const key = t === 'y-awareness' ? opts.keys.awareness : opts.keys.sync
    const { iv, bytes } = await encryptGcm(key, plaintext)
    return { t, iv, bytes }
  }

  async function decryptIfNeeded(
    peer: PeerState,
    msg: CollabWireMessage,
  ): Promise<Uint8Array | null> {
    const bytes =
      msg.bytes instanceof Uint8Array ? msg.bytes : new Uint8Array(msg.bytes)
    // The rule is symmetric: if we settled on E2EE with this peer,
    // frames without an ``iv`` are dropped (could be a downgrade
    // attack). If we settled on plaintext, frames WITH ``iv`` are
    // dropped (we can't decrypt anyway, and accepting them would
    // hide a misconfiguration).
    if (peer.useE2ee) {
      if (!msg.iv || !opts.keys) return null
      const iv = msg.iv instanceof Uint8Array ? msg.iv : new Uint8Array(msg.iv)
      const key = msg.t === 'y-awareness' ? opts.keys.awareness : opts.keys.sync
      try {
        return await decryptGcm(key, { iv, bytes })
      } catch {
        // Auth-tag failure or key mismatch — drop.
        return null
      }
    }
    if (msg.iv) return null
    return bytes
  }

  async function broadcast(
    t: 'y-sync-2' | 'y-awareness',
    plaintext: Uint8Array,
  ): Promise<void> {
    // We encrypt per-peer (not once and re-send) because each peer
    // pair may have resolved E2EE differently during a rolling deploy.
    // IV is fresh per call regardless, so nonce-reuse is a non-issue.
    for (const peer of peers.values()) {
      if (!peer.settled) {
        // Queue the plaintext; we'll encrypt-or-not when we flush.
        peer.pendingOut.push({ t, bytes: plaintext })
        continue
      }
      const msg = await encryptIfNeeded(peer, t, plaintext)
      void peer.transport.send(msg).catch(() => {
        /* swallowed */
      })
    }
  }

  const updateHandler = (update: Uint8Array, origin: unknown): void => {
    if (origin === 'remote') return
    void broadcast('y-sync-2', update)
  }
  doc.on('update', updateHandler)

  const awarenessHandler = (_changes: unknown, origin: unknown): void => {
    if (origin === 'remote') return
    const update = encodeAwarenessUpdate(awareness, [awareness.clientID])
    void broadcast('y-awareness', update)
  }
  awareness.on('update', awarenessHandler)

  async function onHelloReceived(peer: PeerState): Promise<void> {
    // Decide outcome: encrypted only if BOTH sides advertised v1.
    peer.useE2ee = selfHasE2ee && peer.theirE2ee
    peer.settled = true

    // Send sync-1 now that we know the ciphertext vs plaintext shape.
    const sv = Y.encodeStateVector(doc)
    const msg = await encryptIfNeeded(peer, 'y-sync-1', sv)
    void peer.transport.send(msg).catch(() => {
      /* swallowed */
    })

    // Flush any queued updates that accumulated during the handshake.
    const queued = peer.pendingOut
    peer.pendingOut = []
    for (const item of queued) {
      if (
        item.t === 'y-sync-2' ||
        item.t === 'y-awareness' ||
        item.t === 'y-sync-1'
      ) {
        const outgoing = await encryptIfNeeded(
          peer,
          item.t as 'y-sync-1' | 'y-sync-2' | 'y-awareness',
          item.bytes,
        )
        void peer.transport.send(outgoing).catch(() => {
          /* swallowed */
        })
      }
    }
  }

  function handleInbound(
    transport: CollabTransport,
    msg: CollabWireMessage,
  ): void {
    const peer = peers.get(transport.peerId)
    if (!peer) return

    if (msg.t === 'y-sync-hello') {
      // The hello payload is a 1-byte advertisement: 0x01 means "v1
      // E2EE", 0x00 means "plaintext only". Small on purpose — future
      // ``{e: ..., ratchet: ...}`` can ride extra bytes.
      const bytes =
        msg.bytes instanceof Uint8Array ? msg.bytes : new Uint8Array(msg.bytes)
      peer.theirE2ee = bytes.byteLength > 0 && bytes[0] === 0x01
      peer.theirHelloReceived = true
      void onHelloReceived(peer)
      return
    }

    // Everything else runs through decrypt-or-passthrough. If the peer
    // hasn't settled yet (hello still outstanding) we drop — any frame
    // arriving before hello would be un-decodable anyway.
    if (!peer.settled) return

    void (async () => {
      const plaintext = await decryptIfNeeded(peer, msg)
      if (plaintext === null) return
      try {
        if (msg.t === 'y-sync-1') {
          const diff = Y.encodeStateAsUpdate(doc, plaintext)
          const outgoing = await encryptIfNeeded(peer, 'y-sync-2', diff)
          void peer.transport.send(outgoing).catch(() => {
            /* swallowed */
          })
        } else if (msg.t === 'y-sync-2') {
          Y.applyUpdate(doc, plaintext, 'remote')
        } else if (msg.t === 'y-awareness') {
          applyAwarenessUpdate(awareness, plaintext, 'remote')
        }
      } catch {
        /* malformed plaintext after decrypt — drop silently */
      }
    })()
  }

  function addPeer(transport: CollabTransport): void {
    if (peers.has(transport.peerId)) {
      removePeer(transport.peerId)
    }
    const state: PeerState = {
      transport,
      unsubscribe: () => {},
      theirHelloReceived: false,
      theirE2ee: false,
      ourHelloSent: false,
      settled: false,
      useE2ee: false,
      pendingOut: [],
    }
    state.unsubscribe = transport.onMessage((m) => handleInbound(transport, m))
    peers.set(transport.peerId, state)

    // Fire our hello first — sync-1 waits until we've seen the peer's
    // hello so we know whether to encrypt it.
    const helloByte = new Uint8Array([selfHasE2ee ? 0x01 : 0x00])
    void transport
      .send({ t: 'y-sync-hello', bytes: helloByte })
      .then(() => {
        state.ourHelloSent = true
      })
      .catch(() => {
        /* swallowed — caller handles connection errors */
      })
  }

  function removePeer(peerId: string): void {
    const entry = peers.get(peerId)
    if (!entry) return
    entry.unsubscribe()
    peers.delete(peerId)
  }

  function peerEncryptionStatus(
    peerId: string,
  ): 'pending' | 'e2ee' | 'plaintext' | null {
    const p = peers.get(peerId)
    if (!p) return null
    if (!p.settled) return 'pending'
    return p.useE2ee ? 'e2ee' : 'plaintext'
  }

  function close(): void {
    for (const { unsubscribe } of peers.values()) unsubscribe()
    peers.clear()
    doc.off('update', updateHandler)
    awareness.off('update', awarenessHandler)
    awareness.destroy()
  }

  return {
    doc,
    awareness,
    addPeer,
    removePeer,
    peerEncryptionStatus,
    close,
  }
}
