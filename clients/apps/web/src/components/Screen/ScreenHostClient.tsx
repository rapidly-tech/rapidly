'use client'

/**
 * Host-side Screen chamber UI.
 *
 * Thin presentational shell over ``useScreenHost``. Not responsible for
 * any signalling / WebRTC logic — only renders based on the hook status
 * and wires a local-preview <video> to the captured MediaStream.
 */

import { Icon } from '@iconify/react'
import { useEffect, useRef, useState } from 'react'

import { useScreenHost } from '@/hooks/screen/useScreenHost'
import { ScreenDisabledError } from '@/utils/screen/api'

export function ScreenHostClient() {
  const host = useScreenHost()
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const [lastInvite, setLastInvite] = useState<string | null>(null)

  // Attach the captured stream to the preview <video> whenever it changes.
  useEffect(() => {
    if (videoRef.current && host.stream) {
      videoRef.current.srcObject = host.stream
    }
  }, [host.stream])

  if (host.error instanceof ScreenDisabledError) {
    return (
      <div className="mx-auto max-w-lg rounded-xl border border-amber-200 bg-amber-50 p-6 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
        <p className="font-medium">Screen sharing is not enabled here.</p>
        <p className="mt-2 text-sm">
          Ask your operator to flip <code>FILE_SHARING_SCREEN_ENABLED</code> on,
          or try another Rapidly instance.
        </p>
      </div>
    )
  }

  if (host.status === 'idle' || host.status === 'closed') {
    return (
      <div className="mx-auto flex max-w-lg flex-col items-center gap-4 rounded-xl border border-slate-200 bg-white p-8 text-center shadow-md dark:border-slate-800 dark:bg-slate-900">
        <Icon
          icon="lucide:monitor-play"
          width={48}
          height={48}
          className="text-emerald-600"
          aria-hidden
        />
        <h1 className="text-xl font-semibold">Share your screen</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          End-to-end encrypted P2P. Up to 10 viewers per session.
        </p>
        <button
          type="button"
          onClick={() => void host.startSharing()}
          className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white shadow transition hover:bg-emerald-700 focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:outline-none"
        >
          Start sharing
        </button>
        {host.status === 'closed' && (
          <p className="text-xs text-slate-400">Session ended.</p>
        )}
      </div>
    )
  }

  if (host.status === 'error') {
    return (
      <div className="mx-auto max-w-lg rounded-xl border border-red-200 bg-red-50 p-6 text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
        <p className="font-medium">Could not start the session.</p>
        <p className="mt-2 text-sm">{host.error?.message ?? 'Unknown error'}</p>
        <button
          type="button"
          onClick={() => void host.startSharing()}
          className="mt-4 rounded-lg border border-red-300 px-3 py-1.5 text-sm hover:bg-red-100 dark:border-red-800 dark:hover:bg-red-900/40"
        >
          Try again
        </button>
      </div>
    )
  }

  // Active / in-flight: show a preview and the invite URL.
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-black shadow dark:border-slate-800">
        {host.stream ? (
          <video
            ref={videoRef}
            autoPlay
            muted
            playsInline
            className="aspect-video w-full bg-black"
          />
        ) : (
          <div className="flex aspect-video items-center justify-center text-slate-500">
            {host.status === 'requesting-display'
              ? 'Choose a screen or window…'
              : 'Starting up…'}
          </div>
        )}
      </div>

      <div className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-white p-4 shadow dark:border-slate-800 dark:bg-slate-900">
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {host.viewerCount === 0
            ? 'Invite someone to watch.'
            : `${host.viewerCount} viewer${host.viewerCount === 1 ? '' : 's'} connected`}
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={async () => {
              const url = await host.copyInvite()
              if (url) setLastInvite(url)
            }}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
          >
            Copy invite link
          </button>
          <button
            type="button"
            onClick={() => void host.stop()}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
          >
            Stop sharing
          </button>
        </div>
        {lastInvite && (
          <p className="truncate rounded bg-slate-50 px-3 py-2 font-mono text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">
            {lastInvite}
          </p>
        )}
      </div>
    </div>
  )
}
