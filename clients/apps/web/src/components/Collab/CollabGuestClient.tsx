'use client'

/**
 * Guest-side Collab chamber UI.
 *
 * Styled with the Rapidly design tokens (glass-elevated cards,
 * rp-text-*, UI-package Button) to match /features/* + file-sharing.
 */

import { Icon } from '@iconify/react'
import Button from '@rapidly-tech/ui/components/forms/Button'
import { useEffect, useState } from 'react'

import { useCollabRoom } from '@/hooks/collab/useCollabRoom'
import { CollabDisabledError } from '@/utils/collab/api'
import {
  decodeInviteFragment,
  type CollabFragmentKeys,
} from '@/utils/collab/invite-fragment'
import { stableColor } from '@/utils/collab/presence'

import { CollabCanvas } from './CollabCanvas'
import { CollabEditor } from './CollabEditor'
import { EncryptionBadge } from './EncryptionBadge'
import { PresenceStrip } from './PresenceStrip'

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

  useEffect(() => {
    if (!token) return
    if (room.status !== 'idle') return
    if (!room.view) return
    void room.joinAsGuest()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, room.status, room.view])

  if (!token) {
    return (
      <WarnCard
        title="Missing invite token."
        body={
          <>
            The link you opened is missing the <code>?t=...</code> parameter.
            Ask the host to resend.
          </>
        }
      />
    )
  }

  if (E2EE_ENABLED && fragmentChecked && !fragmentKeys) {
    return (
      <WarnCard
        title="Missing encryption key."
        body={
          <>
            This invite link is missing the <code>#k=...</code> fragment the
            session needs to stay end-to-end encrypted. Ask the host to copy the
            invite again — some messaging tools strip everything after{' '}
            <code>#</code>.
          </>
        }
      />
    )
  }

  if (room.error instanceof CollabDisabledError) {
    return <WarnCard title="Collab is not enabled here." />
  }

  if (room.status === 'error') {
    return (
      <div className="mx-auto max-w-lg rounded-2xl border border-red-200 bg-red-50 p-6 text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
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
      <div className="glass-elevated mx-auto flex max-w-lg flex-col items-center gap-3 rounded-2xl bg-slate-50 p-8 text-center shadow-xs dark:bg-slate-900">
        <Icon
          icon="lucide:users"
          width={40}
          height={40}
          className="text-emerald-600"
          aria-hidden
        />
        <h1 className="rp-text-primary text-lg font-semibold">
          {room.view?.title ?? 'Collaborative doc'}
        </h1>
        <p className="rp-text-secondary text-sm">Connecting to peer…</p>
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
        <CollabCanvas
          doc={room.doc}
          clientID={room.clientID}
          presence={room.presence ?? undefined}
          publishCursor={
            room.clientID !== null
              ? (point) => {
                  const self = room.clientID as number
                  room.setLocalPresence({
                    user: {
                      id: String(self),
                      name: 'Guest',
                      color: stableColor(self),
                    },
                    ...(point ? { cursor: point } : {}),
                  })
                }
              : undefined
          }
        />
      ) : (
        <CollabEditor doc={room.doc} />
      )}

      <div className="glass-elevated flex items-center justify-end gap-2 rounded-2xl bg-slate-50 p-3 shadow-xs dark:bg-slate-900">
        <Button
          size="sm"
          variant="destructive"
          onClick={() => void room.leave()}
        >
          <Icon icon="lucide:log-out" width={16} height={16} aria-hidden />
          Leave
        </Button>
      </div>
    </div>
  )
}

function WarnCard({ title, body }: { title: string; body?: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-lg rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
      <p className="font-medium">{title}</p>
      {body && <p className="mt-2 text-sm">{body}</p>}
    </div>
  )
}
