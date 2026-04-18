'use client'

/**
 * Guest-side Collab chamber UI.
 *
 * Fetches public view on mount; shows the session title and a Join
 * button. After join, the editor + presence strip identical to host.
 */

import { Icon } from '@iconify/react'
import { useEffect, useState } from 'react'

import { useCollabRoom } from '@/hooks/collab/useCollabRoom'
import { CollabDisabledError } from '@/utils/collab/api'
import {
  decodeInviteFragment,
  type CollabFragmentKeys,
} from '@/utils/collab/invite-fragment'

import { CollabCanvas } from './CollabCanvas'
import { CollabEditor } from './CollabEditor'
import { EncryptionBadge } from './EncryptionBadge'
import { PresenceStrip } from './PresenceStrip'

// v1.1 E2EE is on by default (PR D). When on, guests must land with
// an invite fragment; no fragment → clear error rather than a silent
// downgrade. Set NEXT_PUBLIC_COLLAB_E2EE=false to opt out per the
// host-side flag.
const E2EE_ENABLED = process.env.NEXT_PUBLIC_COLLAB_E2EE !== 'false'

interface Props {
  slug: string
  token: string | null
}

export function CollabGuestClient({ slug, token }: Props) {
  const [fragmentKeys, setFragmentKeys] = useState<CollabFragmentKeys | null>(
    null,
  )
  const [fragmentChecked, setFragmentChecked] = useState(false)

  // Parse the ``#k=...&s=...`` fragment on mount. If absent or
  // malformed the PR 24 handshake gracefully falls back to plaintext
  // on both sides — nothing fails here.
  useEffect(() => {
    if (typeof window === 'undefined') return
    let cancelled = false
    void (async () => {
      const keys = await decodeInviteFragment(window.location.hash)
      if (cancelled) return
      setFragmentKeys(keys)
      setFragmentChecked(true)
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const room = useCollabRoom({
    slug,
    token,
    options: {
      masterKey: fragmentKeys?.masterKey,
      salt: fragmentKeys?.salt,
    },
  })

  // Auto-join as soon as we know we have both slug + token and the
  // public view has resolved. Matches Call's join-on-click policy —
  // but here we have no media permission to gate, so we skip the
  // "Join" click and drop straight into the editor.
  useEffect(() => {
    if (!token) return
    if (room.status !== 'idle') return
    if (!room.view) return
    void room.joinAsGuest()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, room.status, room.view])

  if (!token) {
    return (
      <div className="mx-auto max-w-lg rounded-xl border border-amber-200 bg-amber-50 p-6 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
        <p className="font-medium">Missing invite token.</p>
        <p className="mt-2 text-sm">
          The link you opened is missing the <code>?t=...</code> parameter. Ask
          the host to resend.
        </p>
      </div>
    )
  }

  // Gate joining on fragment presence when E2EE is required. If the
  // fragment was dropped (forwarded via a tool that stripped ``#...``,
  // or the link was edited) the guest would otherwise try to decrypt
  // with no keys and join a non-converging session. Surface that up
  // front so the host knows to resend.
  if (E2EE_ENABLED && fragmentChecked && !fragmentKeys) {
    return (
      <div className="mx-auto max-w-lg rounded-xl border border-amber-200 bg-amber-50 p-6 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
        <p className="font-medium">Missing encryption key.</p>
        <p className="mt-2 text-sm">
          This invite link is missing the <code>#k=...</code> fragment the
          session needs to stay end-to-end encrypted. Ask the host to copy the
          invite again — some messaging tools strip everything after{' '}
          <code>#</code>.
        </p>
      </div>
    )
  }

  if (room.error instanceof CollabDisabledError) {
    return (
      <div className="mx-auto max-w-lg rounded-xl border border-amber-200 bg-amber-50 p-6 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
        <p className="font-medium">Collab is not enabled here.</p>
      </div>
    )
  }

  if (room.status === 'error') {
    return (
      <div className="mx-auto max-w-lg rounded-xl border border-red-200 bg-red-50 p-6 text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
        <p className="font-medium">Couldn&apos;t join this session.</p>
        <p className="mt-2 text-sm">
          {room.error?.message ??
            'Session may have expired or the link has already been used.'}
        </p>
      </div>
    )
  }

  if (room.status !== 'active' || !room.doc) {
    return (
      <div className="mx-auto flex max-w-lg flex-col items-center gap-3 rounded-xl border border-slate-200 bg-white p-8 text-center shadow dark:border-slate-800 dark:bg-slate-900">
        <Icon
          icon="lucide:users"
          width={40}
          height={40}
          className="text-emerald-600"
          aria-hidden
        />
        <h1 className="text-lg font-semibold">
          {room.view?.title ?? 'Collaborative doc'}
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Connecting to peer…
        </p>
      </div>
    )
  }

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-4">
      <div className="flex items-center justify-end">
        <EncryptionBadge state={room.encryption} />
      </div>
      <PresenceStrip peers={room.peers} selfLabel="You" />

      {room.view?.kind === 'canvas' && room.clientID !== null ? (
        <CollabCanvas doc={room.doc} clientID={room.clientID} />
      ) : (
        <CollabEditor doc={room.doc} />
      )}

      <div className="flex items-center justify-end gap-2 rounded-xl border border-slate-200 bg-white p-3 shadow dark:border-slate-800 dark:bg-slate-900">
        <button
          type="button"
          onClick={() => void room.leave()}
          className="flex items-center gap-1.5 rounded-lg bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700"
        >
          <Icon icon="lucide:log-out" width={18} height={18} aria-hidden />
          Leave
        </button>
      </div>
    </div>
  )
}
