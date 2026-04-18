'use client'

/**
 * Guest-side Call chamber UI.
 *
 * Fetches session metadata → asks for camera/mic on "Join" → connects
 * via signaling → shows the remote tile + local tile with the standard
 * mute / camera controls.
 */

import { Icon } from '@iconify/react'

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
      <div className="mx-auto flex max-w-lg flex-col items-center gap-4 rounded-xl border border-slate-200 bg-white p-8 text-center shadow-md dark:border-slate-800 dark:bg-slate-900">
        <Icon
          icon="lucide:phone-incoming"
          width={40}
          height={40}
          className="text-emerald-600"
          aria-hidden
        />
        <h1 className="text-xl font-semibold">
          {room.view?.title ?? 'Join call'}
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          End-to-end encrypted, peer-to-peer.
        </p>
        <button
          type="button"
          onClick={() => void room.joinAsGuest()}
          className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white shadow transition hover:bg-emerald-700 focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:outline-none"
        >
          Join now
        </button>
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
          <div className="flex aspect-video w-full items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
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

      <div className="flex flex-wrap items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white p-3 shadow dark:border-slate-800 dark:bg-slate-900">
        <button
          type="button"
          onClick={room.toggleAudio}
          className={
            'flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition ' +
            (room.audioMuted
              ? 'bg-red-600 text-white hover:bg-red-700'
              : 'border border-slate-300 text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800')
          }
          aria-pressed={room.audioMuted}
        >
          <Icon
            icon={room.audioMuted ? 'lucide:mic-off' : 'lucide:mic'}
            width={18}
            height={18}
            aria-hidden
          />
          {room.audioMuted ? 'Unmute' : 'Mute'}
        </button>

        <button
          type="button"
          onClick={room.toggleVideo}
          className={
            'flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition ' +
            (room.videoOff
              ? 'bg-red-600 text-white hover:bg-red-700'
              : 'border border-slate-300 text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800')
          }
          aria-pressed={room.videoOff}
        >
          <Icon
            icon={room.videoOff ? 'lucide:video-off' : 'lucide:video'}
            width={18}
            height={18}
            aria-hidden
          />
          {room.videoOff ? 'Camera on' : 'Camera off'}
        </button>

        <button
          type="button"
          onClick={() => void room.leave()}
          className="flex items-center gap-1.5 rounded-lg bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700"
        >
          <Icon icon="lucide:phone-off" width={18} height={18} aria-hidden />
          Leave
        </button>
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
      ? 'border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200'
      : tone === 'error'
        ? 'border-red-200 bg-red-50 text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200'
        : 'border-slate-200 bg-white text-slate-800 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200'
  return (
    <div
      className={`mx-auto flex max-w-lg flex-col items-center gap-3 rounded-xl border p-6 text-center shadow-sm ${toneClass}`}
    >
      <Icon icon={icon} width={32} height={32} aria-hidden />
      <p className="font-medium">{title}</p>
      {body && <p className="text-sm">{body}</p>}
    </div>
  )
}
