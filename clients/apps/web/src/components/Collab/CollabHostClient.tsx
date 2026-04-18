'use client'

/**
 * Host-side Collab chamber UI.
 *
 * "Start a doc" → pick kind (text or canvas) → session created →
 * editor with a copy-invite button and a live presence strip. No
 * camera / mic.
 */

import { Icon } from '@iconify/react'
import { useEffect, useState } from 'react'

import { useCollabRoom } from '@/hooks/collab/useCollabRoom'
import { CollabDisabledError, type CollabKind } from '@/utils/collab/api'
import {
  encodeInviteFragment,
  generateFragmentKeys,
  type CollabFragmentKeys,
} from '@/utils/collab/invite-fragment'

import { CollabCanvas } from './CollabCanvas'
import { CollabEditor } from './CollabEditor'
import { PresenceStrip } from './PresenceStrip'

// v1.1 E2EE is on by default (PR D). Set NEXT_PUBLIC_COLLAB_E2EE=false
// to opt out — e.g., for a narrow debugging session or to accommodate
// a known-stale tab. The provider's no-downgrade stance (PR 24 +
// PR 26) means opting out is a per-deployment choice; individual
// guests cannot force a downgrade.
const E2EE_ENABLED = process.env.NEXT_PUBLIC_COLLAB_E2EE !== 'false'

export function CollabHostClient() {
  const [kind, setKind] = useState<CollabKind>('text')
  const [fragmentKeys, setFragmentKeys] = useState<CollabFragmentKeys | null>(
    null,
  )

  // Generate one master/salt pair per host-client mount (fresh session →
  // fresh keys). Web Crypto is browser-only; the effect runs after
  // mount so SSR is unaffected.
  useEffect(() => {
    if (!E2EE_ENABLED) return
    let cancelled = false
    void (async () => {
      const keys = await generateFragmentKeys()
      if (!cancelled) setFragmentKeys(keys)
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const room = useCollabRoom({
    options: {
      kind,
      maxParticipants: 4,
      masterKey: fragmentKeys?.masterKey,
      salt: fragmentKeys?.salt,
    },
  })
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
      <div className="mx-auto flex max-w-lg flex-col items-center gap-5 rounded-xl border border-slate-200 bg-white p-8 text-center shadow-md dark:border-slate-800 dark:bg-slate-900">
        <Icon
          icon="lucide:users"
          width={48}
          height={48}
          className="text-emerald-600"
          aria-hidden
        />
        <h1 className="text-xl font-semibold">Start a collaborative session</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Realtime, peer-to-peer. Up to 4 people today; nothing is saved on our
          servers.
        </p>

        <div
          className="flex w-full items-center gap-2"
          role="radiogroup"
          aria-label="Session kind"
        >
          <KindButton
            active={kind === 'text'}
            onClick={() => setKind('text')}
            icon="lucide:file-text"
            label="Document"
            hint="Textarea bound to a CRDT"
          />
          <KindButton
            active={kind === 'canvas'}
            onClick={() => setKind('canvas')}
            icon="lucide:pen-tool"
            label="Whiteboard"
            hint="Freehand canvas"
          />
        </div>

        <button
          type="button"
          onClick={() => void room.startAsHost()}
          className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white shadow transition hover:bg-emerald-700 focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:outline-none"
        >
          Start session
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

      {room.doc &&
        (kind === 'canvas' && room.clientID !== null ? (
          <CollabCanvas doc={room.doc} clientID={room.clientID} />
        ) : (
          <CollabEditor doc={room.doc} />
        ))}

      <div className="flex flex-wrap items-center justify-end gap-2 rounded-xl border border-slate-200 bg-white p-3 shadow dark:border-slate-800 dark:bg-slate-900">
        <button
          type="button"
          onClick={async () => {
            const url = await room.copyInvite()
            if (!url) return
            // Append the E2EE fragment so the guest can decrypt. The
            // fragment is not sent in the HTTP GET when the guest
            // loads the page — browsers strip it from the request.
            let full = url
            if (fragmentKeys) {
              const fragment = await encodeInviteFragment(fragmentKeys)
              full = `${url}#${fragment}`
              // copyInvite already wrote ``url`` to the clipboard;
              // overwrite with the fragment-bearing version.
              try {
                await navigator.clipboard.writeText(full)
              } catch {
                /* ignore — UI still shows the URL below */
              }
            }
            setLastInvite(full)
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

interface KindButtonProps {
  active: boolean
  onClick: () => void
  icon: string
  label: string
  hint: string
}

function KindButton({ active, onClick, icon, label, hint }: KindButtonProps) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={active}
      onClick={onClick}
      className={
        'flex flex-1 flex-col items-center gap-1 rounded-lg border px-3 py-3 text-sm transition ' +
        (active
          ? 'border-emerald-500 bg-emerald-50 text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100'
          : 'border-slate-200 text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800')
      }
    >
      <Icon icon={icon} width={22} height={22} aria-hidden />
      <span className="font-medium">{label}</span>
      <span className="text-xs text-slate-500 dark:text-slate-400">{hint}</span>
    </button>
  )
}
