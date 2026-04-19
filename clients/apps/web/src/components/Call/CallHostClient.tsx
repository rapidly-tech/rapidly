'use client'

/**
 * Host-side Call chamber UI.
 *
 * "Start a call" → camera/mic permission → session created → room with a
 * local tile, remote tiles as they join, and mute / camera / copy-invite
 * controls.
 */

import { Icon } from '@iconify/react'
import { useState } from 'react'

import { useCallRoom } from '@/hooks/call/useCallRoom'
import { CallDisabledError } from '@/utils/call/api'

import { ParticipantTile } from './ParticipantTile'

export function CallHostClient() {
  const room = useCallRoom({ options: { mode: 'audio_video' } })
  const [lastInvite, setLastInvite] = useState<string | null>(null)

  if (room.error instanceof CallDisabledError) {
    return (
      <div className="mx-auto max-w-lg rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
        <p className="font-medium">Call is not enabled here.</p>
        <p className="mt-2 text-sm">
          Ask your operator to flip <code>FILE_SHARING_CALL_ENABLED</code> on.
        </p>
      </div>
    )
  }

  if (room.status === 'idle' || room.status === 'closed') {
    return (
      <div className="glass-elevated mx-auto flex max-w-lg flex-col items-center gap-4 rounded-2xl bg-slate-50 p-8 text-center shadow-xs dark:bg-slate-900">
        <Icon
          icon="lucide:phone"
          width={48}
          height={48}
          className="text-emerald-600"
          aria-hidden
        />
        <h1 className="text-xl font-semibold">Start a call</h1>
        <p className="rp-text-secondary text-sm">
          End-to-end encrypted, peer-to-peer. 1:1 today; small-group mesh coming
          soon.
        </p>
        <button
          type="button"
          onClick={() => void room.startAsHost()}
          className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white shadow transition hover:bg-emerald-700 focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:outline-none"
        >
          Start call
        </button>
        {room.status === 'closed' && (
          <p className="rp-text-muted text-xs">Call ended.</p>
        )}
      </div>
    )
  }

  if (room.status === 'error') {
    return (
      <div className="mx-auto max-w-lg rounded-2xl border border-red-200 bg-red-50 p-6 text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
        <p className="font-medium">Could not start the call.</p>
        <p className="mt-2 text-sm">
          {room.error?.message ??
            "Couldn't access camera/mic. Check browser permissions."}
        </p>
        <button
          type="button"
          onClick={() => void room.startAsHost()}
          className="mt-4 rounded-lg border border-red-300 px-3 py-1.5 text-sm hover:bg-red-100 dark:border-red-800 dark:hover:bg-red-900/40"
        >
          Try again
        </button>
      </div>
    )
  }

  // Requesting media / connecting / active
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
            Waiting for someone to join…
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
          onClick={async () => {
            const url = await room.copyInvite()
            if (url) setLastInvite(url)
          }}
          className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-700"
        >
          <Icon icon="lucide:link" width={18} height={18} aria-hidden />
          Copy invite
        </button>

        <button
          type="button"
          onClick={() => void room.leave()}
          className="flex items-center gap-1.5 rounded-lg bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700"
        >
          <Icon icon="lucide:phone-off" width={18} height={18} aria-hidden />
          End call
        </button>
      </div>

      {lastInvite && (
        <p className="truncate rounded bg-slate-50 px-3 py-2 font-mono text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">
          {lastInvite}
        </p>
      )}
    </div>
  )
}
