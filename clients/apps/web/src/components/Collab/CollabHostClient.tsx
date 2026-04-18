'use client'

/**
 * Host-side Collab chamber UI.
 *
 * "Start a doc" → session created → editor with a copy-invite button
 * and a live presence strip. No camera / mic — this chamber is text.
 */

import { Icon } from '@iconify/react'
import { useState } from 'react'

import { useCollabRoom } from '@/hooks/collab/useCollabRoom'
import { CollabDisabledError } from '@/utils/collab/api'

import { CollabEditor } from './CollabEditor'
import { PresenceStrip } from './PresenceStrip'

export function CollabHostClient() {
  const room = useCollabRoom({ options: { kind: 'text', maxParticipants: 4 } })
  const [lastInvite, setLastInvite] = useState<string | null>(null)

  if (room.error instanceof CollabDisabledError) {
    return (
      <div className="mx-auto max-w-lg rounded-xl border border-amber-200 bg-amber-50 p-6 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
        <p className="font-medium">Collab is not enabled here.</p>
        <p className="mt-2 text-sm">
          Ask your operator to flip <code>FILE_SHARING_COLLAB_ENABLED</code> on.
        </p>
      </div>
    )
  }

  if (room.status === 'idle' || room.status === 'closed') {
    return (
      <div className="mx-auto flex max-w-lg flex-col items-center gap-4 rounded-xl border border-slate-200 bg-white p-8 text-center shadow-md dark:border-slate-800 dark:bg-slate-900">
        <Icon
          icon="lucide:users"
          width={48}
          height={48}
          className="text-emerald-600"
          aria-hidden
        />
        <h1 className="text-xl font-semibold">Start a collaborative doc</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Realtime text, peer-to-peer. Up to 4 people today; nothing is saved on
          our servers.
        </p>
        <button
          type="button"
          onClick={() => void room.startAsHost()}
          className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white shadow transition hover:bg-emerald-700 focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:outline-none"
        >
          Start doc
        </button>
        {room.status === 'closed' && (
          <p className="text-xs text-slate-400">Session ended.</p>
        )}
      </div>
    )
  }

  if (room.status === 'error') {
    return (
      <div className="mx-auto max-w-lg rounded-xl border border-red-200 bg-red-50 p-6 text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
        <p className="font-medium">Could not start the session.</p>
        <p className="mt-2 text-sm">
          {room.error?.message ?? 'Unknown error.'}
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

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-4">
      <PresenceStrip peers={room.peers} selfLabel="You (host)" />

      {room.doc && <CollabEditor doc={room.doc} />}

      <div className="flex flex-wrap items-center justify-end gap-2 rounded-xl border border-slate-200 bg-white p-3 shadow dark:border-slate-800 dark:bg-slate-900">
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
          <Icon icon="lucide:log-out" width={18} height={18} aria-hidden />
          End session
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
