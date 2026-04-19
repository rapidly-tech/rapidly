'use client'

/**
 * Host-side Call chamber UI.
 *
 * "Start a call" → camera/mic permission → session created → room with a
 * local tile, remote tiles as they join, and mute / camera / copy-invite
 * controls.
 */

import { Icon } from '@iconify/react'
import Button from '@rapidly-tech/ui/components/forms/Button'
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
        <h1 className="rp-text-primary text-xl font-semibold">Start a call</h1>
        <p className="rp-text-secondary text-sm">
          End-to-end encrypted, peer-to-peer. 1:1 today; small-group mesh coming
          soon.
        </p>
        <Button size="lg" onClick={() => void room.startAsHost()}>
          Start call
        </Button>
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
        <Button
          variant="outline"
          size="sm"
          className="mt-4"
          onClick={() => void room.startAsHost()}
        >
          Try again
        </Button>
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
          <div className="rp-text-muted flex aspect-video w-full items-center justify-center rounded-2xl border border-dashed border-(--beige-border)/30 bg-slate-50 text-sm dark:bg-slate-900">
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
          onClick={async () => {
            const url = await room.copyInvite()
            if (url) setLastInvite(url)
          }}
        >
          <Icon icon="lucide:link" width={16} height={16} aria-hidden />
          Copy invite
        </Button>

        <Button
          size="sm"
          variant="destructive"
          onClick={() => void room.leave()}
        >
          <Icon icon="lucide:phone-off" width={16} height={16} aria-hidden />
          End call
        </Button>
      </div>

      {lastInvite && (
        <p className="rp-text-secondary truncate rounded-xl bg-slate-100 px-3 py-2 font-mono text-xs dark:bg-slate-800">
          {lastInvite}
        </p>
      )}
    </div>
  )
}
