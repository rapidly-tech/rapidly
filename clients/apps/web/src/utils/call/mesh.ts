/**
 * Call chamber — N-way participant mesh coordinator (PR 14).
 *
 * Pure logic, no DOM, no PeerDataConnection imports. The coordinator
 * consumes a stream of "known participants" events (the signaling
 * server's participant list) and maintains a Map of ``PeerLike``
 * connections — opening one for every peer that appears, closing one
 * for every peer that leaves.
 *
 * The subtle concern this module solves is "glare": if both peers in a
 * pair try to send an SDP offer at the same time, WebRTC state
 * machines lock up. The tie-breaker is lexicographic — **the lower
 * peer ID sends the offer**. The higher waits for one. That keeps the
 * decision deterministic without a round-trip.
 *
 * Media tracks are injected via the ``attachTracks`` hook on every
 * newly-created connection. Incoming tracks surface through the
 * caller's ``onRemoteTrack`` callback, tagged with the peer they came
 * from so UI can map them to participant tiles.
 */

// ── Ports ──

/** Narrow view of the things we need from a PeerDataConnection. Kept
 *  interface-shaped so tests can pass a fake instead of the real
 *  WebRTC-backed class. */
export interface PeerLike {
  open: boolean
  peer: string
  createOffer(): Promise<void>
  addTrack(track: MediaStreamTrack, stream: MediaStream): unknown
  close(): void
  onOpen: (() => void) | null
  onClose: (() => void) | null
  onTrack:
    | ((track: MediaStreamTrack, streams: readonly MediaStream[]) => void)
    | null
}

/** Factory the coordinator calls every time a new peer appears. The
 *  factory is responsible for wiring signaling offers/answers/ICE
 *  through to the returned object — the coordinator only orchestrates. */
export type PeerFactory = (remotePeerId: string) => PeerLike

/** Map key is the remote peer ID; value is the live connection. */
export type PeerMap = ReadonlyMap<string, PeerLike>

export interface MeshOptions {
  /** ``performance.now()``-like clock used for logging + tests. */
  now?: () => number
}

export interface MeshCallbacks {
  /** Called once when a fresh ``PeerLike`` is created. Useful for the
   *  caller to attach any per-connection state — logs, stats hooks,
   *  UI badges. */
  onPeerAdded?: (peerId: string, conn: PeerLike) => void
  /** Called when a peer leaves and their connection is torn down. */
  onPeerRemoved?: (peerId: string) => void
  /** Called on every inbound track from any peer. */
  onRemoteTrack?: (
    peerId: string,
    track: MediaStreamTrack,
    streams: readonly MediaStream[],
  ) => void
}

// ── Tie-breaker ──

/** Should ``self`` be the one to send an offer to ``remote``?
 *
 * Lexicographic comparison on the peer IDs (which are ``crypto.randomUUID``
 * in production and any string in tests). Using the bare comparison
 * operator is enough — both peers run the same code and reach opposite
 * decisions every time. */
export function shouldInitiateOffer(self: string, remote: string): boolean {
  return self < remote
}

// ── Coordinator ──

export interface Mesh {
  /** Drive the mesh from a fresh participant-list snapshot. The
   *  coordinator diffs against its current set and opens / closes as
   *  needed. Idempotent — calling with the same list twice is a no-op. */
  setParticipants(peerIds: readonly string[]): void
  /** The live connection map, keyed by peer ID. Exposed read-only so
   *  the UI layer can iterate for its tile grid. */
  readonly peers: PeerMap
  /** Tear every connection down. Called on hook unmount. */
  close(): void
  /** Attach a local track to every current + future peer. Typical use:
   *  one call per audio track and one per video track right after
   *  ``getUserMedia`` resolves. */
  publishTrack(track: MediaStreamTrack, stream: MediaStream): void
}

export function createMesh(
  selfPeerId: string,
  createConnection: PeerFactory,
  callbacks: MeshCallbacks = {},
  _opts: MeshOptions = {},
): Mesh {
  const peers = new Map<string, PeerLike>()
  // Remember every local track we've been asked to publish so new
  // peers joining mid-call receive them without the caller having to
  // republish on every participant event.
  const publishedTracks: Array<{
    track: MediaStreamTrack
    stream: MediaStream
  }> = []

  function attachPublishedTracks(conn: PeerLike): void {
    for (const { track, stream } of publishedTracks) {
      conn.addTrack(track, stream)
    }
  }

  function addPeer(remoteId: string): void {
    const conn = createConnection(remoteId)
    peers.set(remoteId, conn)

    conn.onTrack = (track, streams) => {
      callbacks.onRemoteTrack?.(remoteId, track, streams)
    }
    conn.onClose = () => {
      peers.delete(remoteId)
      callbacks.onPeerRemoved?.(remoteId)
    }

    attachPublishedTracks(conn)
    callbacks.onPeerAdded?.(remoteId, conn)

    // Tie-breaker: only one side initiates. The other side will
    // receive an offer via the signaling dispatcher the caller set up,
    // which will create its own conn + handleOffer.
    if (shouldInitiateOffer(selfPeerId, remoteId)) {
      void conn.createOffer()
    }
  }

  function removePeer(remoteId: string): void {
    const conn = peers.get(remoteId)
    if (!conn) return
    try {
      conn.close()
    } catch {
      /* the onClose callback fires delete + onPeerRemoved; ignore errors */
    }
    // Defensive: onClose should have cleaned up, but the fake
    // PeerDataConnection in some code paths might not fire it.
    if (peers.has(remoteId)) {
      peers.delete(remoteId)
      callbacks.onPeerRemoved?.(remoteId)
    }
  }

  return {
    get peers(): PeerMap {
      return peers
    },

    setParticipants(ids) {
      const targetSet = new Set(ids.filter((id) => id !== selfPeerId))
      // Remove peers that disappeared from the roster.
      for (const existing of [...peers.keys()]) {
        if (!targetSet.has(existing)) removePeer(existing)
      }
      // Add peers that appeared.
      for (const id of targetSet) {
        if (!peers.has(id)) addPeer(id)
      }
    },

    publishTrack(track, stream) {
      publishedTracks.push({ track, stream })
      // Push the new track to every existing open connection.
      for (const conn of peers.values()) {
        conn.addTrack(track, stream)
      }
    },

    close() {
      for (const id of [...peers.keys()]) removePeer(id)
      publishedTracks.length = 0
    },
  }
}
