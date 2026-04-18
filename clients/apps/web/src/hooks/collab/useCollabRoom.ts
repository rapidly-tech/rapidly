/**
 * Collab chamber — room orchestration hook (PR 18).
 *
 * Wires together:
 *   - ``createSession`` (host only) or ``getPublicView`` (guest).
 *   - ``SignalingClient`` connection as host or guest.
 *   - The PR 14 mesh coordinator, with a factory that produces real
 *     ``PeerDataConnection`` instances wired to the signaling dispatcher.
 *   - The PR 17 ``CollabRoom`` (Yjs provider) — one per tab, shared
 *     across all peer transports in this session.
 *
 * Shape mirrors ``useCallRoom`` so the page layer reads identically.
 * The key difference is that Collab does not touch ``getUserMedia`` —
 * the only tracks are CRDT updates over each peer's data channel.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import * as Y from 'yjs'

import { createMesh, type Mesh, type PeerLike } from '@/utils/call/mesh'
import {
  CollabDisabledError,
  closeSession,
  createSession,
  getPublicView,
  mintInvite,
  type CollabKind,
  type CollabSessionPublicView,
  type CreateSessionResponse,
} from '@/utils/collab/api'
import {
  aggregateEncryptionState,
  type PeerStatus,
  type RoomEncryptionState,
} from '@/utils/collab/encryption-state'
import {
  createCollabRoom,
  deriveCollabKeys,
  isCollabMessage,
  type CollabRoom,
  type CollabSessionKeys,
  type CollabTransport,
} from '@/utils/collab/provider'
import { FILE_SHARING_SIGNAL_PATH } from '@/utils/file-sharing/constants'
import { PeerDataConnection } from '@/utils/p2p/peer-connection'
import { SignalingClient, type SignalingMessage } from '@/utils/p2p/signaling'

export type RoomStatus =
  | 'idle'
  | 'creating-session'
  | 'connecting-signaling'
  | 'active'
  | 'closed'
  | 'error'

export interface UseCollabRoomOptions {
  /** Host-only: title shown to guests. */
  title?: string
  /** Host-only: document kind. ``text`` binds a textarea; ``canvas``
   *  unlocks the PR 19 whiteboard if it ships. */
  kind?: CollabKind
  /** Host-only: mesh ceiling. Server accepts [2, 8]. */
  maxParticipants?: number
  /** E2EE master key + salt. Host generates fresh pair on
   *  ``startAsHost``; guest receives via URL fragment. Omitted →
   *  plaintext (v1). See specs/collab-e2ee.md. */
  masterKey?: CryptoKey
  salt?: Uint8Array
}

export interface UseCollabRoomReturn {
  status: RoomStatus
  error: Error | null
  /** The Y.Doc — ``undefined`` until ``active``. Bind editors / observers
   *  to the returned reference (stable for the hook's lifetime once set). */
  doc: Y.Doc | null
  /** Our local Yjs ``clientID`` — used for stroke author tagging in the
   *  whiteboard editor. ``null`` until the room exists. */
  clientID: number | null
  /** Live awareness state per remote client (keyed by Yjs clientID). */
  peers: ReadonlyArray<{ clientID: number; state: Record<string, unknown> }>
  /** Aggregate E2EE state across every connected peer. UI renders a
   *  badge from this; see utils/collab/encryption-state.ts for the
   *  aggregation rules. */
  encryption: RoomEncryptionState
  /** Host-only: the session metadata after create. */
  session: CreateSessionResponse | null
  /** Guest-only: public view fetched on mount. */
  view: CollabSessionPublicView | null
  startAsHost: () => Promise<void>
  joinAsGuest: () => Promise<void>
  copyInvite: () => Promise<string | null>
  setLocalPresence: (state: Record<string, unknown>) => void
  leave: () => Promise<void>
}

export interface UseCollabRoomProps {
  slug?: string | null
  token?: string | null
  options?: UseCollabRoomOptions
}

// ── Transport adapter ──

/** Wrap a ``PeerDataConnection`` as a ``CollabTransport``.
 *
 *  The DC has a single ``onData`` slot. In Collab rooms the DC is ours
 *  alone (no file / screen / watch multiplexing on the same channel),
 *  so we take ownership and dispatch to any subscribed handlers.
 *
 *  We could multiplex by inspecting ``msg.t`` if a future PR needs
 *  it — for now KISS. */
function adaptPeerToTransport(
  peerId: string,
  conn: PeerDataConnection,
): {
  transport: CollabTransport
  detach: () => void
} {
  const handlers = new Set<(msg: { t: string; bytes: Uint8Array }) => void>()
  conn.onData = (data: unknown) => {
    if (!isCollabMessage(data)) return
    // Normalise to Uint8Array — some transport paths surface ArrayBuffer.
    const bytes =
      data.bytes instanceof Uint8Array ? data.bytes : new Uint8Array(data.bytes)
    const normalised = { t: data.t, bytes }
    for (const h of handlers) h(normalised)
  }
  const transport: CollabTransport = {
    peerId,
    async send(msg) {
      await conn.send(msg)
    },
    onMessage(h) {
      handlers.add(h)
      return () => {
        handlers.delete(h)
      }
    },
  }
  return {
    transport,
    detach: () => {
      handlers.clear()
      conn.onData = null
    },
  }
}

export function useCollabRoom(props: UseCollabRoomProps): UseCollabRoomReturn {
  const { slug, token, options } = props
  const role: 'host' | 'guest' = slug && token ? 'guest' : 'host'

  const [status, setStatus] = useState<RoomStatus>('idle')
  const [error, setError] = useState<Error | null>(null)
  const [doc, setDoc] = useState<Y.Doc | null>(null)
  const [clientID, setClientID] = useState<number | null>(null)
  const [peers, setPeers] = useState<
    ReadonlyArray<{ clientID: number; state: Record<string, unknown> }>
  >([])
  const [encryption, setEncryption] = useState<RoomEncryptionState>('solo')
  const [session, setSession] = useState<CreateSessionResponse | null>(null)
  const [view, setView] = useState<CollabSessionPublicView | null>(null)

  const signalingRef = useRef<SignalingClient | null>(null)
  const meshRef = useRef<Mesh | null>(null)
  const roomRef = useRef<CollabRoom | null>(null)
  const sessionRef = useRef<CreateSessionResponse | null>(null)
  const detachersRef = useRef<Map<string, () => void>>(new Map())
  const encryptionTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const refreshPeers = useCallback(() => {
    const room = roomRef.current
    if (!room) return setPeers([])
    const entries: { clientID: number; state: Record<string, unknown> }[] = []
    for (const [clientID, state] of room.awareness.getStates().entries()) {
      if (clientID === room.awareness.clientID) continue
      entries.push({ clientID, state: state as Record<string, unknown> })
    }
    setPeers(entries)
  }, [])

  const leave = useCallback(async () => {
    for (const detach of detachersRef.current.values()) detach()
    detachersRef.current.clear()
    roomRef.current?.close()
    roomRef.current = null
    meshRef.current?.close()
    meshRef.current = null
    signalingRef.current?.close()
    signalingRef.current = null
    if (encryptionTimerRef.current !== null) {
      clearInterval(encryptionTimerRef.current)
      encryptionTimerRef.current = null
    }
    setDoc(null)
    setClientID(null)
    setPeers([])
    setEncryption('solo')
    if (sessionRef.current) {
      try {
        await closeSession(
          sessionRef.current.short_slug,
          sessionRef.current.secret,
        )
      } catch {
        /* best-effort — host may have already navigated away */
      }
      sessionRef.current = null
      setSession(null)
    }
    setStatus('closed')
  }, [])

  /** Shared setup once signaling's ``welcome`` frame resolves. */
  async function bootstrap(
    signaling: SignalingClient,
    selfId: string,
    iceServers: RTCIceServer[],
  ): Promise<void> {
    // Derive E2EE sub-keys if both master + salt are present. Missing
    // either → plaintext fallback (handshake negotiates).
    let keys: CollabSessionKeys | undefined
    if (options?.masterKey && options?.salt) {
      keys = await deriveCollabKeys(options.masterKey, options.salt)
    }

    const room = createCollabRoom({ selfPeerId: selfId, keys })
    roomRef.current = room
    setDoc(room.doc)
    setClientID(room.awareness.clientID)
    room.awareness.on('change', refreshPeers)

    // Re-aggregate encryption state periodically. The handshake
    // resolves asynchronously and without a dedicated event, so a
    // light poll is the simplest path to a correct-eventually UI
    // indicator. 500 ms is fast enough that a user never reads the
    // "pending" pill unless the network is genuinely slow.
    encryptionTimerRef.current = setInterval(() => {
      const r = roomRef.current
      if (!r) return
      const statuses: PeerStatus[] = []
      for (const peerId of detachersRef.current.keys()) {
        const s = r.peerEncryptionStatus(peerId)
        if (s) statuses.push(s)
      }
      setEncryption(aggregateEncryptionState(statuses))
    }, 500)

    const mesh = createMesh(
      selfId,
      (remoteId: string) => {
        const conn = new PeerDataConnection(signaling, iceServers, remoteId)
        // Wire the transport as soon as the DC opens — before that,
        // ``conn.send`` throws. ``onOpen`` is fired exactly once per
        // connection lifetime so there's no re-entry risk.
        const { transport, detach } = adaptPeerToTransport(remoteId, conn)
        conn.onOpen = () => {
          room.addPeer(transport)
        }
        conn.onClose = () => {
          room.removePeer(remoteId)
          detach()
          detachersRef.current.delete(remoteId)
        }
        detachersRef.current.set(remoteId, detach)
        return conn as unknown as PeerLike
      },
      {
        onPeerRemoved: (peerId) => {
          room.removePeer(peerId)
          const detach = detachersRef.current.get(peerId)
          if (detach) {
            detach()
            detachersRef.current.delete(peerId)
          }
        },
      },
    )
    meshRef.current = mesh

    // Route signaling frames to the right PeerDataConnection. Mirror of
    // the dispatcher used in useCallRoom — identical semantics because
    // the transport layer is shared.
    signaling.onMessage = async (msg: SignalingMessage) => {
      const fromId = msg.fromId as string | undefined
      if (!fromId) return
      if (msg.type === 'connect-request') {
        mesh.setParticipants([selfId, ...mesh.peers.keys(), fromId])
        return
      }
      if (msg.type === 'peer-left') {
        const peerId = msg.peerId as string | undefined
        if (peerId) {
          mesh.setParticipants(
            [...mesh.peers.keys(), selfId].filter((id) => id !== peerId),
          )
        }
        return
      }
      if (
        msg.type === 'offer' ||
        msg.type === 'answer' ||
        msg.type === 'ice-candidate'
      ) {
        if (!mesh.peers.has(fromId)) {
          mesh.setParticipants([selfId, ...mesh.peers.keys(), fromId])
        }
        const conn = mesh.peers.get(fromId) as unknown as
          | PeerDataConnection
          | undefined
        if (!conn) return
        if (msg.type === 'offer') await conn.handleOffer(msg.sdp as string)
        else if (msg.type === 'answer')
          await conn.handleAnswer(msg.sdp as string)
        else {
          await conn.handleIceCandidate({
            candidate: msg.candidate as string,
            sdpMid: msg.sdpMid as string | null,
            sdpMLineIndex: msg.sdpMLineIndex as number | null,
          })
        }
      }
    }

    signaling.onClose = () => setStatus('closed')
  }

  const startAsHost = useCallback(async () => {
    setError(null)
    try {
      setStatus('creating-session')
      const created = await createSession(
        options?.title ?? null,
        options?.maxParticipants ?? 4,
        options?.kind ?? 'text',
      )
      sessionRef.current = created
      setSession(created)

      setStatus('connecting-signaling')
      const signaling = new SignalingClient(FILE_SHARING_SIGNAL_PATH)
      signalingRef.current = signaling
      const welcome = await signaling.connect(
        created.short_slug,
        'host',
        created.secret,
      )
      await bootstrap(signaling, welcome.peerId, welcome.iceServers)
      setStatus('active')
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)))
      setStatus('error')
      await leave()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options?.title, options?.kind, options?.maxParticipants, leave])

  const joinAsGuest = useCallback(async () => {
    if (!slug || !token) {
      setError(new Error('Missing session slug or invite token'))
      setStatus('error')
      return
    }
    setError(null)
    try {
      setStatus('connecting-signaling')
      const signaling = new SignalingClient(FILE_SHARING_SIGNAL_PATH)
      signalingRef.current = signaling
      const welcome = await signaling.connect(slug, 'guest', token)
      await bootstrap(signaling, welcome.peerId, welcome.iceServers)
      signaling.send({ type: 'connect-request' })
      setStatus('active')
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)))
      setStatus('error')
      await leave()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug, token, leave])

  const copyInvite = useCallback(async (): Promise<string | null> => {
    const current = sessionRef.current
    if (!current) return null
    const mint = await mintInvite(current.short_slug, current.secret)
    const url = new URL(mint.invite_url, window.location.origin).toString()
    try {
      await navigator.clipboard.writeText(url)
    } catch {
      /* ignore — caller still gets the URL */
    }
    return url
  }, [])

  const setLocalPresence = useCallback((state: Record<string, unknown>) => {
    const room = roomRef.current
    if (!room) return
    room.awareness.setLocalState(state)
  }, [])

  // Guest: fetch public view on mount so the join screen can show the
  // session title / kind before committing to a connection.
  useEffect(() => {
    if (role !== 'guest' || !slug) return
    let cancelled = false
    void (async () => {
      try {
        const v = await getPublicView(slug)
        if (!cancelled) setView(v)
      } catch (err) {
        if (!cancelled)
          setError(err instanceof Error ? err : new Error(String(err)))
      }
    })()
    return () => {
      cancelled = true
    }
  }, [role, slug])

  useEffect(() => {
    return () => {
      void leave()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return {
    status,
    error,
    doc,
    clientID,
    peers,
    session,
    view,
    encryption,
    startAsHost,
    joinAsGuest,
    copyInvite,
    setLocalPresence,
    leave,
  }
}

export { CollabDisabledError }
