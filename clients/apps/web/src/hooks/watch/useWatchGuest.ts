/**
 * Guest-side orchestration for the Watch chamber.
 *
 * Flow: GET /session/{slug} for source_url + metadata → connect signaling
 * with invite token → open a PeerDataConnection to the host → on every
 * inbound SyncMessage, feed it to the sync guest which reconciles the
 * local <video>.
 *
 * The local <video> element is provided by the component; the hook
 * attaches a SyncMediaController to it the moment the caller signals
 * readiness via ``setVideo``.
 */

import { FILE_SHARING_SIGNAL_PATH } from '@/utils/file-sharing/constants'
import { PeerDataConnection } from '@/utils/p2p/peer-connection'
import { SignalingClient, type SignalingMessage } from '@/utils/p2p/signaling'
import { getPublicView, type WatchSessionPublicView } from '@/utils/watch/api'
import {
  createSyncGuest,
  isSyncMessage,
  type SyncGuest,
  type SyncMessage,
} from '@/utils/watch/sync-protocol'
import { createVideoController } from '@/utils/watch/video-controller'
import { useCallback, useEffect, useRef, useState } from 'react'

export type GuestStatus =
  | 'loading'
  | 'ready'
  | 'connecting'
  | 'active'
  | 'ended'
  | 'error'

export interface UseWatchGuestReturn {
  status: GuestStatus
  error: Error | null
  view: WatchSessionPublicView | null
  /** Call when the local <video> ref is populated so the sync guest can
   *  attach its controller. Pass ``null`` on unmount. */
  setVideo: (video: HTMLVideoElement | null) => void
  join: () => Promise<void>
  leave: () => void
}

export function useWatchGuest(
  slug: string | null,
  token: string | null,
): UseWatchGuestReturn {
  const [status, setStatus] = useState<GuestStatus>('loading')
  const [error, setError] = useState<Error | null>(null)
  const [view, setView] = useState<WatchSessionPublicView | null>(null)

  const signalingRef = useRef<SignalingClient | null>(null)
  const connRef = useRef<PeerDataConnection | null>(null)
  const syncGuestRef = useRef<SyncGuest | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const controllerDisposeRef = useRef<(() => void) | null>(null)

  const setVideo = useCallback((video: HTMLVideoElement | null) => {
    // Tear any previous controller down before switching.
    controllerDisposeRef.current?.()
    controllerDisposeRef.current = null
    syncGuestRef.current?.stop()
    syncGuestRef.current = null

    videoRef.current = video
    if (!video) return

    const controller = createVideoController(video)
    controllerDisposeRef.current = () => controller.dispose()
    syncGuestRef.current = createSyncGuest(controller, (msg) => {
      if (connRef.current?.open) {
        void connRef.current.send(msg as unknown as Record<string, unknown>)
      }
    })
  }, [])

  const leave = useCallback(() => {
    syncGuestRef.current?.stop()
    syncGuestRef.current = null
    controllerDisposeRef.current?.()
    controllerDisposeRef.current = null
    connRef.current?.close()
    connRef.current = null
    signalingRef.current?.close()
    signalingRef.current = null
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

      const ensureConn = (peerId: string): PeerDataConnection => {
        if (connRef.current) return connRef.current
        const conn = new PeerDataConnection(
          signaling,
          welcome.iceServers,
          peerId,
        )
        conn.onData = (data: unknown) => {
          if (isSyncMessage(data)) {
            syncGuestRef.current?.apply(data as SyncMessage)
          }
        }
        conn.onClose = () => setStatus('ended')
        connRef.current = conn
        return conn
      }

      signaling.onMessage = async (msg: SignalingMessage) => {
        const fromId = msg.fromId as string | undefined
        if (!fromId) return
        if (msg.type === 'offer') {
          await ensureConn(fromId).handleOffer(msg.sdp as string)
        } else if (msg.type === 'answer') {
          await ensureConn(fromId).handleAnswer(msg.sdp as string)
        } else if (msg.type === 'ice-candidate') {
          await ensureConn(fromId).handleIceCandidate({
            candidate: msg.candidate as string,
            sdpMid: msg.sdpMid as string | null,
            sdpMLineIndex: msg.sdpMLineIndex as number | null,
          })
        } else if (msg.type === 'host-available') {
          // Host is online — we initiate the offer.
          await ensureConn(fromId).createOffer()
        }
      }
      signaling.onClose = () => {
        setStatus((prev) => (prev === 'active' ? 'ended' : prev))
      }
      setStatus('active')
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)))
      setStatus('error')
    }
  }, [slug, token])

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

  return { status, error, view, setVideo, join, leave }
}
