'use client'

/**
 * Host-side Watch chamber UI.
 *
 * Caller pastes a video URL, clicks Start, and the local <video> plays
 * normally — every play / pause / seek is mirrored to connected guests
 * via the PR 10 sync protocol.
 */

import { Icon } from '@iconify/react'
import Button from '@rapidly-tech/ui/components/forms/Button'
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
      <div className="mx-auto max-w-lg rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
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
        className="glass-elevated mx-auto flex max-w-lg flex-col items-center gap-4 rounded-2xl bg-slate-50 p-8 text-center shadow-xs dark:bg-slate-900"
      >
        <Icon
          icon="lucide:play"
          width={48}
          height={48}
          className="text-emerald-600"
          aria-hidden
        />
        <p className="rp-text-secondary text-sm">
          Paste a video URL. Up to 10 viewers, perfectly synced.
        </p>
        <input
          type="url"
          required
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com/video.mp4"
          className="rp-text-primary placeholder:rp-text-muted w-full rounded-xl border border-(--beige-border)/30 bg-white px-3 py-2 text-sm focus:ring-2 focus:ring-slate-400 focus:outline-none dark:border-white/6 dark:bg-white/3"
        />
        {/* The <video> exists even before Start so the host hook has a
         *  ref to attach a controller to when start() fires. */}
        <video
          ref={videoRef}
          className="hidden"
          preload="metadata"
          playsInline
        />
        <Button type="submit" size="lg" disabled={!url}>
          Start watching
        </Button>
        {host.status === 'closed' && (
          <p className="rp-text-muted text-xs">Session ended.</p>
        )}
      </form>
    )
  }

  if (host.status === 'error') {
    return (
      <div className="mx-auto max-w-lg rounded-2xl border border-red-200 bg-red-50 p-6 text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
        <p className="font-medium">Could not start the session.</p>
        <p className="mt-2 text-sm">{host.error?.message ?? 'Unknown error'}</p>
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div className="glass-elevated overflow-hidden rounded-2xl bg-black shadow-xs">
        <video
          ref={videoRef}
          controls
          autoPlay
          playsInline
          className="aspect-video w-full bg-black"
        />
      </div>

      <div className="glass-elevated flex flex-col gap-2 rounded-2xl bg-slate-50 p-4 shadow-xs dark:bg-slate-900">
        <p className="rp-text-secondary text-sm">
          {host.viewerCount === 0
            ? 'Invite someone to join.'
            : `${host.viewerCount} viewer${host.viewerCount === 1 ? '' : 's'} connected`}
        </p>
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={async () => {
              const inviteUrl = await host.copyInvite()
              if (inviteUrl) setLastInvite(inviteUrl)
            }}
          >
            Copy invite link
          </Button>
          <Button size="sm" variant="outline" onClick={() => void host.stop()}>
            End session
          </Button>
        </div>
        {lastInvite && (
          <p className="rp-text-secondary truncate rounded-xl bg-slate-100 px-3 py-2 font-mono text-xs dark:bg-slate-800">
            {lastInvite}
          </p>
        )}
      </div>
    </div>
  )
}
