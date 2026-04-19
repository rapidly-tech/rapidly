/**
 * Host-side orchestration for the Screen chamber.
 *
 * Ties together: getDisplayMedia → POST /session → SignalingClient → one
 * PeerDataConnection per guest + addTrack. Returns a small state machine
 * the component layer renders off of.
 *
 * The hook does NOT own the DOM — it exposes the captured MediaStream so
 * the caller can attach it to a <video> element for local preview.
 */

import { FILE_SHARING_SIGNAL_PATH } from '@/utils/file-sharing/constants'
import { PeerDataConnection } from '@/utils/p2p/peer-connection'
import { SignalingClient, type SignalingMessage } from '@/utils/p2p/signaling'
import {
  closeSession,
  createSession,
  mintInvite,
  type CreateSessionResponse,
} from '@/utils/screen/api'
import { useCallback, useEffect, useRef, useState } from 'react'

export type HostStatus =
  | 'idle'
  | 'requesting-display'
  | 'creating-session'
  | 'connecting-signaling'
  | 'active'
  | 'closed'
  | 'error'

export interface UseScreenHostReturn {
  status: HostStatus
  error: Error | null
  session: CreateSessionResponse | null
  stream: MediaStream | null
  viewerCount: number
  startSharing: () => Promise<void>
  copyInvite: () => Promise<string | null>
  stop: () => Promise<void>
}

export function useScreenHost(options?: {
  title?: string | null
  maxViewers?: number
}): UseScreenHostReturn {
  const [status, setStatus] = useState<HostStatus>('idle')
  const [error, setError] = useState<Error | null>(null)
  const [session, setSession] = useState<CreateSessionResponse | null>(null)
  const [stream, setStream] = useState<MediaStream | null>(null)
  const [viewerCount, setViewerCount] = useState(0)

  const signalingRef = useRef<SignalingClient | null>(null)
  const connsRef = useRef<Map<string, PeerDataConnection>>(new Map())
  const streamRef = useRef<MediaStream | null>(null)
  const sessionRef = useRef<CreateSessionResponse | null>(null)

  const stop = useCallback(async () => {
    // Tear everything down in reverse order of how we built it.
    for (const conn of connsRef.current.values()) conn.close()
    connsRef.current.clear()
    setViewerCount(0)

    signalingRef.current?.close()
    signalingRef.current = null

    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    setStream(null)

    if (sessionRef.current) {
      try {
        await closeSession(
          sessionRef.current.short_slug,
          sessionRef.current.secret,
        )
      } catch {
        // Best-effort: the session TTL handles cleanup if the DELETE fails.
      }
      sessionRef.current = null
      setSession(null)
    }
    setStatus('closed')
  }, [])

  const startSharing = useCallback(async () => {
    setError(null)
    try {
      // 1. Ask for the display stream. User may cancel.
      setStatus('requesting-display')
      const captured = await navigator.mediaDevices.getDisplayMedia({
        video: true,
        audio: false,
      })
      streamRef.current = captured
      setStream(captured)
      // If the user stops the share via the browser's "Stop sharing" bar,
      // the track ends and we tear down the session.
      captured.getVideoTracks()[0]?.addEventListener('ended', () => {
        void stop()
      })

      // 2. Create the session on the backend.
      setStatus('creating-session')
      const created = await createSession(
        options?.title ?? null,
        options?.maxViewers ?? 10,
      )
      sessionRef.current = created
      setSession(created)

      // 3. Open the signaling WebSocket as host.
      setStatus('connecting-signaling')
      const signaling = new SignalingClient(FILE_SHARING_SIGNAL_PATH)
      signalingRef.current = signaling
      const welcome = await signaling.connect(
        created.short_slug,
        'host',
        created.secret,
      )

      // 4. Wire message routing: each new guest gets a fresh
      //    PeerDataConnection we answer / track-add onto.
      signaling.onMessage = (msg: SignalingMessage) =>
        void handleSignalingMessage(msg, welcome.iceServers)
      signaling.onClose = () => {
        // Signaling drop: keep local stream but mark closed so UI can react.
        setStatus('closed')
      }

      setStatus('active')
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)))
      setStatus('error')
      await stop()
    }
  }, [options?.title, options?.maxViewers, stop])

  /**
   * Handle one signaling message. New guests arrive as 'offer' messages.
   * We answer each one and attach the live stream's tracks to the new
   * connection.
   */
  async function handleSignalingMessage(
    msg: SignalingMessage,
    iceServers: RTCIceServer[],
  ): Promise<void> {
    const stream = streamRef.current
    if (!stream) return

    const fromId = msg.fromId as string | undefined
    if (!fromId) return

    if (msg.type === 'connect-request') {
      // Guest wants in. Build a fresh peer connection, attach the
      // live tracks, and initiate the offer from our side. The shared
      // signaling server only relays the four WebRTC messages +
      // ``connect-request``; there is no server-side ``host-available``
      // notification, so the guest bootstrapping path is always a
      // ``connect-request`` from the new peer.
      const conn = new PeerDataConnection(
        signalingRef.current!,
        iceServers,
        fromId,
      )
      for (const track of stream.getTracks()) conn.addTrack(track, stream)
      connsRef.current.set(fromId, conn)
      setViewerCount(connsRef.current.size)
      conn.onClose = () => {
        connsRef.current.delete(fromId)
        setViewerCount(connsRef.current.size)
      }
      await conn.createOffer()
      return
    }

    if (msg.type === 'answer') {
      const conn = connsRef.current.get(fromId)
      if (conn) await conn.handleAnswer(msg.sdp as string)
      return
    }

    if (msg.type === 'ice-candidate') {
      const conn = connsRef.current.get(fromId)
      if (conn) {
        await conn.handleIceCandidate({
          candidate: msg.candidate as string,
          sdpMid: msg.sdpMid as string | null,
          sdpMLineIndex: msg.sdpMLineIndex as number | null,
        })
      }
    }
  }

  /** Mint a fresh invite token and return the full shareable URL. */
  const copyInvite = useCallback(async (): Promise<string | null> => {
    const current = sessionRef.current
    if (!current) return null
    const mint = await mintInvite(current.short_slug, current.secret)
    const url = new URL(mint.invite_url, window.location.origin).toString()
    try {
      await navigator.clipboard.writeText(url)
    } catch {
      // Clipboard API can fail in non-secure contexts — the caller still
      // receives the URL and can surface a fallback "copy manually".
    }
    return url
  }, [])

  // Tear down on unmount.
  useEffect(() => {
    return () => {
      void stop()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return {
    status,
    error,
    session,
    stream,
    viewerCount,
    startSharing,
    copyInvite,
    stop,
  }
}
