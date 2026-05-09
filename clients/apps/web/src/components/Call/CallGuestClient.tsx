'use client'

/**
 * Guest-side Call chamber UI.
 *
 * Fetches session metadata → asks for camera/mic on "Join" → connects
 * via signaling → shows the remote tile + local tile with the standard
 * mute / camera controls.
 */

import { Icon } from '@iconify/react'
import Button from '@rapidly-tech/ui/components/forms/Button'

import { useCallRoom } from '@/hooks/call/useCallRoom'

import { ParticipantTile } from './ParticipantTile'

interface CallGuestClientProps {
  slug: string
  token: string | null
}

export function CallGuestClient({ slug, token }: CallGuestClientProps) {
  const room = useCallRoom({ slug, token })

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

  if (room.status === 'error') {
    return (
      <Message
        icon="lucide:alert-octagon"
        tone="error"
        title="Couldn't join the call"
        body={room.error?.message ?? 'Unknown error'}
      />
    )
  }

  if (room.status === 'closed') {
    return (
      <Message
        icon="lucide:phone-off"
        title="Call ended"
        body="The host ended the call."
      />
    )
  }

  // Show join screen only when we haven't attempted yet.
  if (room.status === 'idle') {
    return (
      <div className="glass-elevated mx-auto flex max-w-lg flex-col items-center gap-4 rounded-2xl bg-slate-50 p-8 text-center shadow-xs dark:bg-slate-900">
        <Icon
          icon="lucide:phone-incoming"
          width={40}
          height={40}
          className="text-emerald-600"
          aria-hidden
        />
        <h1 className="rp-text-primary text-xl font-semibold">
          {room.view?.title ?? 'Join call'}
        </h1>
        <p className="rp-text-secondary text-sm">
          End-to-end encrypted, peer-to-peer.
        </p>
        <Button size="lg" onClick={() => void room.joinAsGuest()}>
          Join now
        </Button>
      </div>
    )
  }

  const remoteEntries = Array.from(room.remoteStreams.entries())
  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <ParticipantTile
          stream={room.localStream}
          label="You"
          muted
          videoOff={room.videoOff}
        />
        {remoteEntries.length === 0 ? (
          <div className="rp-text-muted flex aspect-video w-full items-center justify-center rounded-2xl border border-dashed border-(--beige-border)/30 bg-slate-50 text-sm dark:bg-slate-900">
            Connecting…
          </div>
        ) : (
          remoteEntries.map(([peerId, stream]) => (
            <ParticipantTile
              key={peerId}
              stream={stream}
              label={`Participant ${peerId.slice(0, 6)}`}
            />
          ))
        )}
      </div>

      <div className="glass-elevated flex flex-wrap items-center justify-center gap-2 rounded-2xl bg-slate-50 p-3 shadow-xs dark:bg-slate-900">
        <Button
          size="sm"
          variant={room.audioMuted ? 'destructive' : 'outline'}
          onClick={room.toggleAudio}
          aria-pressed={room.audioMuted}
        >
          <Icon
            icon={room.audioMuted ? 'lucide:mic-off' : 'lucide:mic'}
            width={16}
            height={16}
            aria-hidden
          />
          {room.audioMuted ? 'Unmute' : 'Mute'}
        </Button>

        <Button
          size="sm"
          variant={room.videoOff ? 'destructive' : 'outline'}
          onClick={room.toggleVideo}
          aria-pressed={room.videoOff}
        >
          <Icon
            icon={room.videoOff ? 'lucide:video-off' : 'lucide:video'}
            width={16}
            height={16}
            aria-hidden
          />
          {room.videoOff ? 'Camera on' : 'Camera off'}
        </Button>

        <Button
          size="sm"
          variant="destructive"
          onClick={() => void room.leave()}
        >
          <Icon icon="lucide:phone-off" width={16} height={16} aria-hidden />
          Leave
        </Button>
      </div>
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
