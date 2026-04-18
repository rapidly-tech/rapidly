/**
 * Host-side orchestration for the Watch chamber.
 *
 * Flow: caller provides a URL + a ref to a <video> element → hook calls
 * POST /session, opens signaling as host, and on each new guest: opens a
 * PeerDataConnection, answers the offer, subscribes the sync host to
 * ``conn.send`` so every ``state`` / ``seek`` message fans out to that
 * guest.
 *
 * The local <video> is the source of truth for playback state. The sync
 * host reads from a ``SyncMediaController`` backed by that element.
 */

import { FILE_SHARING_SIGNAL_PATH } from '@/utils/file-sharing/constants'
import { PeerDataConnection } from '@/utils/p2p/peer-connection'
import { SignalingClient, type SignalingMessage } from '@/utils/p2p/signaling'
import {
  WatchDisabledError,
  closeSession,
  createSession,
  mintInvite,
  type CreateSessionResponse,
} from '@/utils/watch/api'
import {
  createSyncHost,
  type SyncHost,
  type SyncMessage,
} from '@/utils/watch/sync-protocol'
import { createVideoController } from '@/utils/watch/video-controller'
import { useCallback, useEffect, useRef, useState } from 'react'

export type HostStatus =
  | 'idle'
  | 'creating-session'
  | 'connecting-signaling'
  | 'active'
  | 'closed'
  | 'error'

export interface UseWatchHostReturn {
  status: HostStatus
  error: Error | null
  session: CreateSessionResponse | null
  viewerCount: number
  start: (opts: {
    url: string
    title?: string
    maxViewers?: number
    video: HTMLVideoElement
  }) => Promise<void>
  copyInvite: () => Promise<string | null>
  stop: () => Promise<void>
}

export function useWatchHost(): UseWatchHostReturn {
  const [status, setStatus] = useState<HostStatus>('idle')
  const [error, setError] = useState<Error | null>(null)
  const [session, setSession] = useState<CreateSessionResponse | null>(null)
  const [viewerCount, setViewerCount] = useState(0)

  const signalingRef = useRef<SignalingClient | null>(null)
  const connsRef = useRef<Map<string, PeerDataConnection>>(new Map())
  const sessionRef = useRef<CreateSessionResponse | null>(null)
  const syncHostRef = useRef<SyncHost | null>(null)
  const controllerDisposeRef = useRef<(() => void) | null>(null)

  /** Broadcast one sync message to every connected guest. */
  const broadcast = useCallback((msg: SyncMessage): void => {
    for (const conn of connsRef.current.values()) {
      if (conn.open) void conn.send(msg as unknown as Record<string, unknown>)
    }
  }, [])

  const stop = useCallback(async () => {
    syncHostRef.current?.stop()
    syncHostRef.current = null
    controllerDisposeRef.current?.()
    controllerDisposeRef.current = null

    for (const conn of connsRef.current.values()) conn.close()
    connsRef.current.clear()
    setViewerCount(0)

    signalingRef.current?.close()
    signalingRef.current = null

    if (sessionRef.current) {
      try {
        await closeSession(
          sessionRef.current.short_slug,
          sessionRef.current.secret,
        )
      } catch {
        // Best-effort — TTL handles cleanup if DELETE fails.
      }
      sessionRef.current = null
      setSession(null)
    }
    setStatus('closed')
  }, [])

  const start = useCallback(
    async ({
      url,
      title,
      maxViewers,
      video,
    }: {
      url: string
      title?: string
      maxViewers?: number
      video: HTMLVideoElement
    }) => {
      setError(null)
      try {
        setStatus('creating-session')
        const created = await createSession(
          title ?? null,
          maxViewers ?? 10,
          url,
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

        // Sync host observes the local <video> and hands every outbound
        // message to the broadcaster.
        const controller = createVideoController(video)
        controllerDisposeRef.current = () => controller.dispose()
        syncHostRef.current = createSyncHost(controller, broadcast)

        signaling.onMessage = (msg: SignalingMessage) =>
          void handleSignalingMessage(msg, welcome.iceServers)
        signaling.onClose = () => setStatus('closed')

        setStatus('active')
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)))
        setStatus(err instanceof WatchDisabledError ? 'error' : 'error')
        await stop()
      }
    },
    [broadcast, stop],
  )

  /** Route signaling frames to the right PeerDataConnection per guest. */
  async function handleSignalingMessage(
    msg: SignalingMessage,
    iceServers: RTCIceServer[],
  ): Promise<void> {
    const fromId = msg.fromId as string | undefined
    if (!fromId) return

    if (msg.type === 'offer') {
      const conn = new PeerDataConnection(
        signalingRef.current!,
        iceServers,
        fromId,
      )
      connsRef.current.set(fromId, conn)
      setViewerCount(connsRef.current.size)
      conn.onOpen = () => {
        // New guest is DC-open; push current state immediately so they
        // converge without waiting for the next heartbeat.
        syncHostRef.current?.broadcastState()
      }
      conn.onClose = () => {
        connsRef.current.delete(fromId)
        setViewerCount(connsRef.current.size)
      }
      await conn.handleOffer(msg.sdp as string)
      return
    }

    const conn = connsRef.current.get(fromId)
    if (!conn) return
    if (msg.type === 'answer') {
      await conn.handleAnswer(msg.sdp as string)
    } else if (msg.type === 'ice-candidate') {
      await conn.handleIceCandidate({
        candidate: msg.candidate as string,
        sdpMid: msg.sdpMid as string | null,
        sdpMLineIndex: msg.sdpMLineIndex as number | null,
      })
    }
  }

  const copyInvite = useCallback(async (): Promise<string | null> => {
    const current = sessionRef.current
    if (!current) return null
    const mint = await mintInvite(current.short_slug, current.secret)
    const url = new URL(mint.invite_url, window.location.origin).toString()
    try {
      await navigator.clipboard.writeText(url)
    } catch {
      /* fallback path — caller still gets the URL */
    }
    return url
  }, [])

  useEffect(() => {
    return () => {
      void stop()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { status, error, session, viewerCount, start, copyInvite, stop }
}
