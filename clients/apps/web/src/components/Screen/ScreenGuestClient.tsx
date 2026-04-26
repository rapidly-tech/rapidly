'use client'

/**
 * Guest-side Screen chamber UI.
 *
 * Receives the remote stream from ``useScreenGuest`` and renders it in a
 * <video> element. Handles the loading / ready / ended states explicitly
 * so the operator does not have to guess what state the session is in.
 */

import { Icon } from '@iconify/react'
import Button from '@rapidly-tech/ui/components/forms/Button'
import { useEffect, useRef } from 'react'

import { useScreenGuest } from '@/hooks/screen/useScreenGuest'

interface ScreenGuestClientProps {
  slug: string
  token: string | null
}

export function ScreenGuestClient({ slug, token }: ScreenGuestClientProps) {
  const guest = useScreenGuest(slug, token)
  const videoRef = useRef<HTMLVideoElement | null>(null)

  useEffect(() => {
    if (videoRef.current && guest.stream) {
      videoRef.current.srcObject = guest.stream
    }
  }, [guest.stream])

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
        icon="lucide:monitor-off"
        title="Session ended"
        body="The host has stopped sharing."
      />
    )
  }

  if (guest.status === 'ready') {
    return (
      <div className="glass-elevated mx-auto flex max-w-lg flex-col items-center gap-4 rounded-2xl bg-slate-50 p-8 text-center shadow-xs dark:bg-slate-900">
        <Icon
          icon="lucide:monitor"
          width={40}
          height={40}
          className="text-emerald-600"
          aria-hidden
        />
        <h1 className="rp-text-primary text-xl font-semibold">
          {guest.view?.title ?? 'Screen share'}
        </h1>
        <p className="rp-text-secondary text-sm">
          Up to {guest.view?.max_viewers ?? 10} viewers · hosted on rapidly.tech
        </p>
        <Button size="lg" onClick={() => void guest.join()}>
          Join now
        </Button>
      </div>
    )
  }

  // connecting / active
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-3">
      <div className="glass-elevated overflow-hidden rounded-2xl bg-black shadow-xs">
        {guest.status === 'active' && guest.stream ? (
          <video
            ref={videoRef}
            autoPlay
            playsInline
            className="aspect-video w-full bg-black"
          />
        ) : (
          <div className="rp-text-muted flex aspect-video items-center justify-center">
            Connecting…
          </div>
        )}
      </div>
      <p className="rp-text-muted text-center text-xs">
        Connected peer-to-peer.
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
