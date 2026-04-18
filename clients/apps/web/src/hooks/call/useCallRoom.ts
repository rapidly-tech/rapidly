/**
 * Call chamber — room orchestration hook (PR 15).
 *
 * Wires together:
 *   - ``createSession`` (host only) or ``getPublicView`` (guest).
 *   - ``SignalingClient`` connection as host or guest.
 *   - ``getUserMedia`` for the local audio + video tracks.
 *   - The PR 14 mesh coordinator, with a factory that produces real
 *     ``PeerDataConnection`` instances wired to the signaling message
 *     dispatcher.
 *
 * v1 ships 1:1 calls (2 participants). The mesh coordinator supports
 * N-way; the remaining piece for ≥3 participants is a roster broadcast
 * from the signaling server so late joiners learn about existing peers.
 * That's tracked as a follow-up.
 */

import {
  CallDisabledError,
  closeSession,
  createSession,
  getPublicView,
  mintInvite,
  type CallMode,
  type CallSessionPublicView,
  type CreateSessionResponse,
} from '@/utils/call/api'
import { createMesh, type Mesh, type PeerLike } from '@/utils/call/mesh'
import { FILE_SHARING_SIGNAL_PATH } from '@/utils/file-sharing/constants'
import { PeerDataConnection } from '@/utils/p2p/peer-connection'
import { SignalingClient, type SignalingMessage } from '@/utils/p2p/signaling'
import { useCallback, useEffect, useRef, useState } from 'react'

export type RoomStatus =
  | 'idle'
  | 'requesting-media'
  | 'creating-session'
  | 'connecting-signaling'
  | 'active'
  | 'closed'
  | 'error'

export interface RemoteTrackEvent {
  peerId: string
  track: MediaStreamTrack
  stream: MediaStream
}

export interface UseCallRoomOptions {
  /** Host-only: the session we're creating. Not passed on the guest side. */
  mode?: CallMode
  /** Host-only: label shown to guests. */
  title?: string
}

export interface UseCallRoomReturn {
  status: RoomStatus
  error: Error | null
  localStream: MediaStream | null
  /** Keyed by remote peer id. Mirrored into React state for render. */
  remoteStreams: ReadonlyMap<string, MediaStream>
  audioMuted: boolean
  videoOff: boolean
  /** Host-only: the session's invite template after create. */
  session: CreateSessionResponse | null
  /** Guest-only: the public metadata fetched on mount. */
  view: CallSessionPublicView | null
  startAsHost: () => Promise<void>
  joinAsGuest: () => Promise<void>
  toggleAudio: () => void
  toggleVideo: () => void
  copyInvite: () => Promise<string | null>
  leave: () => Promise<void>
}

export interface UseCallRoomProps {
  /** Host session parameters, or a `slug`+`token` pair for guest mode. */
  slug?: string | null
  token?: string | null
  options?: UseCallRoomOptions
}

export function useCallRoom(props: UseCallRoomProps): UseCallRoomReturn {
  const { slug, token, options } = props
  const role: 'host' | 'guest' = slug && token ? 'guest' : 'host'

  const [status, setStatus] = useState<RoomStatus>('idle')
  const [error, setError] = useState<Error | null>(null)
  const [localStream, setLocalStream] = useState<MediaStream | null>(null)
  const [remoteStreams, setRemoteStreams] = useState<
    ReadonlyMap<string, MediaStream>
  >(new Map())
  const [audioMuted, setAudioMuted] = useState(false)
  const [videoOff, setVideoOff] = useState(false)
  const [session, setSession] = useState<CreateSessionResponse | null>(null)
  const [view, setView] = useState<CallSessionPublicView | null>(null)

  const signalingRef = useRef<SignalingClient | null>(null)
  const meshRef = useRef<Mesh | null>(null)
  const localStreamRef = useRef<MediaStream | null>(null)
  const sessionRef = useRef<CreateSessionResponse | null>(null)
  const remoteStreamsRef = useRef<Map<string, MediaStream>>(new Map())

  const bumpRemote = useCallback(() => {
    // Shallow-copy the ref into a fresh Map so React notices the change.
    setRemoteStreams(new Map(remoteStreamsRef.current))
  }, [])

  /** Shared factory produces real PeerDataConnections for the mesh. */
  const buildFactory = useCallback(
    (signaling: SignalingClient, iceServers: RTCIceServer[]) =>
      (remoteId: string): PeerLike => {
        const conn = new PeerDataConnection(signaling, iceServers, remoteId)
        return conn as unknown as PeerLike
      },
    [],
  )

  const leave = useCallback(async () => {
    meshRef.current?.close()
    meshRef.current = null
    signalingRef.current?.close()
    signalingRef.current = null
    localStreamRef.current?.getTracks().forEach((t) => t.stop())
    localStreamRef.current = null
    setLocalStream(null)
    remoteStreamsRef.current.clear()
    setRemoteStreams(new Map())
    if (sessionRef.current) {
      try {
        await closeSession(
          sessionRef.current.short_slug,
          sessionRef.current.secret,
        )
      } catch {
        /* best-effort */
      }
      sessionRef.current = null
      setSession(null)
    }
    setStatus('closed')
  }, [])

  /** Common setup after we know the signaling welcome. Creates the mesh,
   *  requests media, wires the signaling → mesh message dispatcher. */
  async function bootstrap(
    signaling: SignalingClient,
    selfId: string,
    iceServers: RTCIceServer[],
    mode: CallMode,
  ): Promise<void> {
    // 1. Request media.
    setStatus('requesting-media')
    const constraints: MediaStreamConstraints = {
      audio: true,
      video: mode === 'audio_video',
    }
    const captured = await navigator.mediaDevices.getUserMedia(constraints)
    localStreamRef.current = captured
    setLocalStream(captured)

    // 2. Create the mesh coordinator wired to the signaling client.
    const factory = buildFactory(signaling, iceServers)
    const mesh = createMesh(selfId, factory, {
      onRemoteTrack: (peerId, track, streams) => {
        const stream = streams[0] ?? new MediaStream([track])
        remoteStreamsRef.current.set(peerId, stream)
        bumpRemote()
      },
      onPeerRemoved: (peerId) => {
        remoteStreamsRef.current.delete(peerId)
        bumpRemote()
      },
    })
    meshRef.current = mesh

    // 3. Publish every local track to every current + future peer.
    for (const track of captured.getTracks()) {
      mesh.publishTrack(track, captured)
    }

    // 4. Route signaling frames to the right PeerDataConnection.
    signaling.onMessage = async (msg: SignalingMessage) => {
      const fromId = msg.fromId as string | undefined
      if (!fromId) return
      if (msg.type === 'connect-request') {
        // Host-side: a guest announced itself. Add to mesh + initiate
        // via the tie-breaker (lower peer ID offers).
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
        // Make sure the mesh knows about fromId so the factory has
        // already created the PeerDataConnection (and attached tracks).
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
        2, // v1 caps at 2 participants; raise when mesh roster ships.
        options?.mode ?? 'audio_video',
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

      await bootstrap(
        signaling,
        welcome.peerId,
        welcome.iceServers,
        options?.mode ?? 'audio_video',
      )
      setStatus('active')
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)))
      setStatus(err instanceof CallDisabledError ? 'error' : 'error')
      await leave()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options?.title, options?.mode, leave])

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

      await bootstrap(
        signaling,
        welcome.peerId,
        welcome.iceServers,
        (view?.mode as CallMode | undefined) ?? 'audio_video',
      )
      // Announce ourselves so the host adds us to its mesh and initiates
      // offer/answer. The existing file-sharing signaling server routes
      // this to the room's host automatically.
      signaling.send({ type: 'connect-request' })
      setStatus('active')
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)))
      setStatus('error')
      await leave()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug, token, view?.mode, leave])

  const toggleAudio = useCallback(() => {
    const stream = localStreamRef.current
    if (!stream) return
    const next = !audioMuted
    for (const track of stream.getAudioTracks()) track.enabled = !next
    setAudioMuted(next)
  }, [audioMuted])

  const toggleVideo = useCallback(() => {
    const stream = localStreamRef.current
    if (!stream) return
    const next = !videoOff
    for (const track of stream.getVideoTracks()) track.enabled = !next
    setVideoOff(next)
  }, [videoOff])

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

  // Fetch public view on mount for guests, for the join screen.
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
    localStream,
    remoteStreams,
    audioMuted,
    videoOff,
    session,
    view,
    startAsHost,
    joinAsGuest,
    toggleAudio,
    toggleVideo,
    copyInvite,
    leave,
  }
}
