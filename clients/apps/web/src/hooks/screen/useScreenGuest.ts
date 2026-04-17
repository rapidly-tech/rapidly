/**
 * Guest-side orchestration for the Screen chamber.
 *
 * Flow: GET /session/{slug} → connect signaling as guest with invite
 * token → create a fresh PeerDataConnection, send an offer, receive
 * tracks via onTrack, expose them to the caller as a single MediaStream.
 */

import { FILE_SHARING_SIGNAL_PATH } from '@/utils/file-sharing/constants'
import { PeerDataConnection } from '@/utils/p2p/peer-connection'
import { SignalingClient, type SignalingMessage } from '@/utils/p2p/signaling'
import { getPublicView, type ScreenSessionPublicView } from '@/utils/screen/api'
import { useCallback, useEffect, useRef, useState } from 'react'

export type GuestStatus =
  | 'loading'
  | 'ready'
  | 'connecting'
  | 'active'
  | 'ended'
  | 'error'

export interface UseScreenGuestReturn {
  status: GuestStatus
  error: Error | null
  view: ScreenSessionPublicView | null
  stream: MediaStream | null
  join: () => Promise<void>
  leave: () => void
}

export function useScreenGuest(
  slug: string | null,
  token: string | null,
): UseScreenGuestReturn {
  const [status, setStatus] = useState<GuestStatus>('loading')
  const [error, setError] = useState<Error | null>(null)
  const [view, setView] = useState<ScreenSessionPublicView | null>(null)
  const [stream, setStream] = useState<MediaStream | null>(null)

  const signalingRef = useRef<SignalingClient | null>(null)
  const connRef = useRef<PeerDataConnection | null>(null)
  const streamRef = useRef<MediaStream | null>(null)

  const leave = useCallback(() => {
    connRef.current?.close()
    connRef.current = null
    signalingRef.current?.close()
    signalingRef.current = null
    streamRef.current = null
    setStream(null)
    setStatus('ended')
  }, [])

  const join = useCallback(async () => {
    if (!slug || !token) {
      setError(new Error('Missing session slug or invite token'))
      setStatus('error')
      return
    }
    setError(null)
    try {
      setStatus('connecting')
      const signaling = new SignalingClient(FILE_SHARING_SIGNAL_PATH)
      signalingRef.current = signaling
      const welcome = await signaling.connect(slug, 'guest', token)

      // Create a PeerDataConnection pinned to the host's peer id (learned
      // from the first 'host-available' or 'offer' message — the file
      // sharing protocol sends a 'host' or 'welcome' payload that points
      // at the host's peer id. For the minimum UI we lazily create the
      // connection on the first signaling message and remember whom we're
      // talking to.
      let hostPeerId: string | null = null

      const ensureConn = (peerId: string): PeerDataConnection => {
        if (connRef.current) return connRef.current
        const conn = new PeerDataConnection(
          signaling,
          welcome.iceServers,
          peerId,
        )
        conn.onTrack = (track, streams) => {
          const incoming = streams[0] ?? new MediaStream([track])
          streamRef.current = incoming
          setStream(incoming)
          setStatus('active')
        }
        conn.onClose = () => {
          if (streamRef.current) {
            setStream(null)
            streamRef.current = null
          }
          setStatus('ended')
        }
        connRef.current = conn
        return conn
      }

      signaling.onMessage = async (msg: SignalingMessage) => {
        const fromId = msg.fromId as string | undefined

        // Host announces presence with a 'host-available' or arrives via
        // first offer. Either way, pin the host peer id on first sight.
        if (fromId && !hostPeerId) hostPeerId = fromId

        if (msg.type === 'offer' && fromId) {
          const conn = ensureConn(fromId)
          await conn.handleOffer(msg.sdp as string)
        } else if (msg.type === 'answer' && fromId) {
          const conn = ensureConn(fromId)
          await conn.handleAnswer(msg.sdp as string)
        } else if (msg.type === 'ice-candidate' && fromId) {
          const conn = ensureConn(fromId)
          await conn.handleIceCandidate({
            candidate: msg.candidate as string,
            sdpMid: msg.sdpMid as string | null,
            sdpMLineIndex: msg.sdpMLineIndex as number | null,
          })
        } else if (msg.type === 'host-available' && fromId) {
          // Host is online — initiate the offer from our side by creating a
          // connection and calling createOffer(). The host will answer.
          const conn = ensureConn(fromId)
          await conn.createOffer()
        }
      }

      signaling.onClose = () => {
        setStatus((prev) => (prev === 'active' ? 'ended' : prev))
      }
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)))
      setStatus('error')
    }
  }, [slug, token])

  // Fetch the public view metadata on mount so the UI can render a "join"
  // screen with the session title + viewer cap before connecting.
  useEffect(() => {
    if (!slug) return
    let cancelled = false
    void (async () => {
      try {
        const v = await getPublicView(slug)
        if (!cancelled) {
          setView(v)
          setStatus('ready')
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err : new Error(String(err)))
          setStatus('error')
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [slug])

  useEffect(() => {
    return () => leave()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { status, error, view, stream, join, leave }
}
