'use client'

/**
 * Guest-side Watch chamber UI.
 *
 * Renders the source URL in a local <video> element; the sync guest
 * reconciles playback state against inbound messages from the host.
 */

import { Icon } from '@iconify/react'
import Button from '@rapidly-tech/ui/components/forms/Button'
import { useCallback } from 'react'

import { useWatchGuest } from '@/hooks/watch/useWatchGuest'

/** Mirror the host-side guard. Return the normalized URL or ``null`` so
 *  the render path hands only a sanitized value to ``<video src>``. */
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

interface WatchGuestClientProps {
  slug: string
  token: string | null
}

export function WatchGuestClient({ slug, token }: WatchGuestClientProps) {
  const guest = useWatchGuest(slug, token)

  const attachVideoRef = useCallback(
    (node: HTMLVideoElement | null) => {
      guest.setVideo(node)
    },
    [guest],
  )

  if (!token) {
    return (
      <Message
        icon="lucide:alert-triangle"
        tone="warn"
        title="Invite link is incomplete"
        body="This link is missing its invite token. Ask the host to resend the full URL."
      />
    )
  }

  if (guest.status === 'loading') {
    return <Message icon="lucide:loader" title="Loading session…" />
  }

  if (guest.status === 'error') {
    return (
      <Message
        icon="lucide:alert-octagon"
        tone="error"
        title="Couldn't join the session"
        body={guest.error?.message ?? 'Unknown error'}
      />
    )
  }

  if (guest.status === 'ended') {
    return (
      <Message
        icon="lucide:stop-circle"
        title="Session ended"
        body="The host has stopped the watch party."
      />
    )
  }

  if (guest.status === 'ready') {
    return (
      <div className="glass-elevated mx-auto flex max-w-lg flex-col items-center gap-4 rounded-2xl bg-slate-50 p-8 text-center shadow-xs dark:bg-slate-900">
        <Icon
          icon="lucide:play"
          width={40}
          height={40}
          className="text-emerald-600"
          aria-hidden
        />
        <h1 className="rp-text-primary text-xl font-semibold">
          {guest.view?.title ?? 'Watch together'}
        </h1>
        <p className="rp-text-secondary text-sm">
          Up to {guest.view?.max_viewers ?? 10} viewers · synced to the host
        </p>
        <Button size="lg" onClick={() => void guest.join()}>
          Join now
        </Button>
      </div>
    )
  }

  // connecting / active — render the <video> so the controller attaches.
  const safeSrc = guest.view?.source_url
    ? sanitizeVideoUrl(guest.view.source_url)
    : null
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-3">
      <div className="glass-elevated overflow-hidden rounded-2xl bg-black shadow-xs">
        {safeSrc ? (
          <video
            ref={attachVideoRef}
            src={safeSrc}
            playsInline
            // No ``controls`` — the guest cannot steer playback; that's
            // the whole product promise of a synced watch party.
            className="aspect-video w-full bg-black"
          />
        ) : (
          <div className="rp-text-muted flex aspect-video items-center justify-center">
            {guest.view?.source_url
              ? 'Host sent an unsupported URL.'
              : 'Host has not set a video URL yet.'}
          </div>
        )}
      </div>
      <p className="rp-text-muted text-center text-xs">
        {guest.status === 'active' ? 'Synced to the host.' : 'Connecting…'}
      </p>
    </div>
  )
}

interface MessageProps {
  icon: string
  title: string
  body?: string
  tone?: 'info' | 'warn' | 'error'
}

function Message({ icon, title, body, tone = 'info' }: MessageProps) {
  const toneClass =
    tone === 'warn'
      ? 'border border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200'
      : tone === 'error'
        ? 'border border-red-200 bg-red-50 text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200'
        : 'glass-elevated rp-text-primary bg-slate-50 dark:bg-slate-900'
  return (
    <div
      className={`mx-auto flex max-w-lg flex-col items-center gap-3 rounded-2xl p-6 text-center shadow-xs ${toneClass}`}
    >
      <Icon icon={icon} width={32} height={32} aria-hidden />
      <p className="font-medium">{title}</p>
      {body && <p className="text-sm">{body}</p>}
    </div>
  )
}
