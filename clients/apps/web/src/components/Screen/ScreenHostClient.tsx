'use client'

/**
 * Host-side Screen chamber UI.
 *
 * Thin presentational shell over ``useScreenHost``. Not responsible for
 * any signalling / WebRTC logic — only renders based on the hook status
 * and wires a local-preview <video> to the captured MediaStream.
 */

import { Icon } from '@iconify/react'
import Button from '@rapidly-tech/ui/components/forms/Button'
import { useEffect, useRef, useState } from 'react'

import { useScreenHost } from '@/hooks/screen/useScreenHost'
import { ScreenDisabledError } from '@/utils/screen/api'

/** Screen capture is only possible on browsers that ship getDisplayMedia.
 *  iOS Safari does not — Apple restricts tab/window capture on iPhone +
 *  iPad. We check the capability up-front so we can render an honest
 *  "not supported on this device" panel instead of silently failing
 *  into "session ended" when the user taps Start sharing. */
function canCaptureDisplay(): boolean {
  if (typeof navigator === 'undefined') return false
  const md = navigator.mediaDevices as
    | (MediaDevices & { getDisplayMedia?: unknown })
    | undefined
  return typeof md?.getDisplayMedia === 'function'
}

export function ScreenHostClient() {
  const host = useScreenHost()
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const [lastInvite, setLastInvite] = useState<string | null>(null)
  const [supported, setSupported] = useState(true)

  // Capability probe runs after hydration so SSR output doesn't depend
  // on a browser-only API (and we can still render the "unsupported"
  // card without mismatching the server render).
  useEffect(() => {
    setSupported(canCaptureDisplay())
  }, [])

  // Attach the captured stream to the preview <video> whenever it changes.
  useEffect(() => {
    if (videoRef.current && host.stream) {
      videoRef.current.srcObject = host.stream
    }
  }, [host.stream])

  if (host.error instanceof ScreenDisabledError) {
    return (
      <div className="mx-auto max-w-lg rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
        <p className="font-medium">Screen sharing is not enabled here.</p>
        <p className="mt-2 text-sm">
          Ask your operator to flip <code>FILE_SHARING_SCREEN_ENABLED</code> on,
          or try another Rapidly instance.
        </p>
      </div>
    )
  }

  if (host.status === 'idle' || host.status === 'closed') {
    if (!supported) {
      return (
        <div className="glass-elevated mx-auto flex max-w-lg flex-col items-center gap-3 rounded-2xl bg-slate-50 p-8 text-center shadow-xs dark:bg-slate-900">
          <Icon
            icon="lucide:smartphone-off"
            width={48}
            height={48}
            className="text-amber-500"
            aria-hidden
          />
          <p className="rp-text-primary text-base font-semibold">
            Screen sharing isn&apos;t supported here
          </p>
          <p className="rp-text-secondary text-sm">
            iOS Safari and older browsers don&apos;t expose a screen-capture
            API. Start the share from a desktop browser (Chrome, Firefox, Edge,
            Safari on macOS) — people on iPhone / iPad can still{' '}
            <strong>join as viewers</strong>.
          </p>
        </div>
      )
    }
    return (
      <div className="glass-elevated mx-auto flex max-w-lg flex-col items-center gap-4 rounded-2xl bg-slate-50 p-8 text-center shadow-xs dark:bg-slate-900">
        <Icon
          icon="lucide:monitor-play"
          width={48}
          height={48}
          className="text-emerald-600"
          aria-hidden
        />
        <p className="rp-text-secondary text-sm">
          End-to-end encrypted P2P. Up to 10 viewers per session.
        </p>
        <Button size="lg" onClick={() => void host.startSharing()}>
          Start sharing
        </Button>
        {host.status === 'closed' && (
          <p className="rp-text-muted text-xs">Session ended.</p>
        )}
      </div>
    )
  }

  if (host.status === 'error') {
    return (
      <div className="mx-auto max-w-lg rounded-2xl border border-red-200 bg-red-50 p-6 text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
        <p className="font-medium">Could not start the session.</p>
        <p className="mt-2 text-sm">{host.error?.message ?? 'Unknown error'}</p>
        <Button
          variant="outline"
          size="sm"
          className="mt-4"
          onClick={() => void host.startSharing()}
        >
          Try again
        </Button>
      </div>
    )
  }

  // Active / in-flight: show a preview and the invite URL.
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div className="glass-elevated overflow-hidden rounded-2xl bg-black shadow-xs">
        {host.stream ? (
          <video
            ref={videoRef}
            autoPlay
            muted
            playsInline
            className="aspect-video w-full bg-black"
          />
        ) : (
          <div className="rp-text-muted flex aspect-video items-center justify-center">
            {host.status === 'requesting-display'
              ? 'Choose a screen or window…'
              : 'Starting up…'}
          </div>
        )}
      </div>

      <div className="glass-elevated flex flex-col gap-2 rounded-2xl bg-slate-50 p-4 shadow-xs dark:bg-slate-900">
        <p className="rp-text-secondary text-sm">
          {host.viewerCount === 0
            ? 'Invite someone to watch.'
            : `${host.viewerCount} viewer${host.viewerCount === 1 ? '' : 's'} connected`}
        </p>
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={async () => {
              const url = await host.copyInvite()
              if (url) setLastInvite(url)
            }}
          >
            Copy invite link
          </Button>
          <Button size="sm" variant="outline" onClick={() => void host.stop()}>
            Stop sharing
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
