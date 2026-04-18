'use client'

/**
 * Host-side Watch chamber UI.
 *
 * Caller pastes a video URL, clicks Start, and the local <video> plays
 * normally — every play / pause / seek is mirrored to connected guests
 * via the PR 10 sync protocol.
 */

import { Icon } from '@iconify/react'
import { useEffect, useRef, useState } from 'react'

import { useWatchHost } from '@/hooks/watch/useWatchHost'
import { WatchDisabledError } from '@/utils/watch/api'

/** Accept only http(s) URLs as video sources, and return the normalized
 *  form so the caller can assign the sanitized value (not the raw input)
 *  to ``video.src``. ``javascript:`` / ``data:`` / relative / malformed
 *  inputs all resolve to ``null``. Returning the sanitized string
 *  instead of a boolean gives static analysers a clear taint boundary. */
function sanitizeVideoUrl(input: string): string | null {
  try {
    const parsed = new URL(input)
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      return null
    }
    return parsed.toString()
  } catch {
    return null
  }
}

export function WatchHostClient() {
  const host = useWatchHost()
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const [url, setUrl] = useState('')
  const [lastInvite, setLastInvite] = useState<string | null>(null)

  // Assign src once the video element is mounted + a URL is present.
  useEffect(() => {
    if (!videoRef.current || host.status !== 'active' || !url) return
    const safe = sanitizeVideoUrl(url)
    if (safe && videoRef.current.src !== safe) {
      videoRef.current.src = safe
    }
  }, [host.status, url])

  if (host.error instanceof WatchDisabledError) {
    return (
      <div className="mx-auto max-w-lg rounded-xl border border-amber-200 bg-amber-50 p-6 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
        <p className="font-medium">Watch Together is not enabled here.</p>
        <p className="mt-2 text-sm">
          Ask your operator to flip <code>FILE_SHARING_WATCH_ENABLED</code> on.
        </p>
      </div>
    )
  }

  if (host.status === 'idle' || host.status === 'closed') {
    return (
      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (!url || !videoRef.current) return
          void host.start({ url, video: videoRef.current })
        }}
        className="mx-auto flex max-w-lg flex-col items-center gap-4 rounded-xl border border-slate-200 bg-white p-8 text-center shadow-md dark:border-slate-800 dark:bg-slate-900"
      >
        <Icon
          icon="lucide:play"
          width={48}
          height={48}
          className="text-emerald-600"
          aria-hidden
        />
        <h1 className="text-xl font-semibold">Watch together</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Paste a video URL. Up to 10 viewers, perfectly synced.
        </p>
        <input
          type="url"
          required
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com/video.mp4"
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800"
        />
        {/* The <video> exists even before Start so the host hook has a
         *  ref to attach a controller to when start() fires. */}
        <video
          ref={videoRef}
          className="hidden"
          preload="metadata"
          playsInline
        />
        <button
          type="submit"
          disabled={!url}
          className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white shadow transition hover:bg-emerald-700 focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:outline-none disabled:opacity-50"
        >
          Start watching
        </button>
        {host.status === 'closed' && (
          <p className="text-xs text-slate-400">Session ended.</p>
        )}
      </form>
    )
  }

  if (host.status === 'error') {
    return (
      <div className="mx-auto max-w-lg rounded-xl border border-red-200 bg-red-50 p-6 text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
        <p className="font-medium">Could not start the session.</p>
        <p className="mt-2 text-sm">{host.error?.message ?? 'Unknown error'}</p>
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-black shadow dark:border-slate-800">
        <video
          ref={videoRef}
          controls
          autoPlay
          playsInline
          className="aspect-video w-full bg-black"
        />
      </div>

      <div className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-white p-4 shadow dark:border-slate-800 dark:bg-slate-900">
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {host.viewerCount === 0
            ? 'Invite someone to join.'
            : `${host.viewerCount} viewer${host.viewerCount === 1 ? '' : 's'} connected`}
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={async () => {
              const inviteUrl = await host.copyInvite()
              if (inviteUrl) setLastInvite(inviteUrl)
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
            End session
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
