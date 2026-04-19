'use client'

/**
 * Host-side Collab chamber UI.
 *
 * Styled with the Rapidly design tokens (glass-elevated cards,
 * rp-text-*, UI-package Button) so this surface looks the same as
 * the file-sharing landing + /features/* pages.
 */

import { Icon } from '@iconify/react'
import Button from '@rapidly-tech/ui/components/forms/Button'
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
import { EncryptionBadge } from './EncryptionBadge'
import { PresenceStrip } from './PresenceStrip'

const E2EE_ENABLED = process.env.NEXT_PUBLIC_COLLAB_E2EE !== 'false'

export function CollabHostClient() {
  const [kind, setKind] = useState<CollabKind>('text')
  const [fragmentKeys, setFragmentKeys] = useState<CollabFragmentKeys | null>(
    null,
  )

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
    return <DisabledCard />
  }

  if (room.status === 'idle' || room.status === 'closed') {
    return (
      <div className="glass-elevated mx-auto flex max-w-lg flex-col items-center gap-5 rounded-2xl bg-slate-50 p-7 text-center shadow-xs dark:bg-slate-900">
        <Icon
          icon="lucide:users"
          width={48}
          height={48}
          className="text-emerald-600"
          aria-hidden
        />
        <p className="rp-text-secondary text-sm">
          Up to 4 people today; nothing is saved on our servers.
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

        <Button size="lg" onClick={() => void room.startAsHost()}>
          Start session
        </Button>
        {room.status === 'closed' && (
          <p className="rp-text-muted text-xs">Session ended.</p>
        )}
      </div>
    )
  }

  if (room.status === 'error') {
    return (
      <div className="mx-auto max-w-lg rounded-2xl border border-red-200 bg-red-50 p-6 text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
        <p className="font-medium">Could not start the session.</p>
        <p className="mt-2 text-sm">
          {room.error?.message ?? 'Unknown error.'}
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

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-4">
      <div className="flex items-center justify-end">
        <EncryptionBadge state={room.encryption} />
      </div>
      <PresenceStrip peers={room.peers} selfLabel="You (host)" />

      {room.doc &&
        (kind === 'canvas' && room.clientID !== null ? (
          <CollabCanvas doc={room.doc} clientID={room.clientID} />
        ) : (
          <CollabEditor doc={room.doc} />
        ))}

      <div className="glass-elevated flex flex-wrap items-center justify-end gap-2 rounded-2xl bg-slate-50 p-3 shadow-xs dark:bg-slate-900">
        <Button
          size="sm"
          onClick={async () => {
            const url = await room.copyInvite()
            if (!url) return
            // Append the E2EE fragment. Browsers strip ``#...`` from
            // HTTP requests, so the server never sees the key.
            let full = url
            if (fragmentKeys) {
              const fragment = await encodeInviteFragment(fragmentKeys)
              full = `${url}#${fragment}`
              try {
                await navigator.clipboard.writeText(full)
              } catch {
                /* ignore — the pill below still shows the URL */
              }
            }
            setLastInvite(full)
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
          <Icon icon="lucide:log-out" width={16} height={16} aria-hidden />
          End session
        </Button>
      </div>

      {lastInvite && (
        <p className="rp-text-secondary truncate rounded-xl bg-slate-50 px-3 py-2 font-mono text-xs dark:bg-slate-800">
          {lastInvite}
        </p>
      )}
    </div>
  )
}

function DisabledCard() {
  return (
    <div className="mx-auto max-w-lg rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
      <p className="font-medium">Collab is not enabled here.</p>
      <p className="mt-2 text-sm">
        Ask your operator to flip <code>FILE_SHARING_COLLAB_ENABLED</code> on.
      </p>
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
        'flex flex-1 flex-col items-center gap-1 rounded-2xl border px-3 py-3 text-sm transition ' +
        (active
          ? 'border-emerald-500 bg-emerald-50 text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100'
          : 'rp-text-secondary hover:rp-text-primary border-(--beige-border)/30 bg-white hover:bg-slate-50 dark:border-white/6 dark:bg-white/3 dark:hover:bg-(--beige-item-hover)')
      }
    >
      <Icon icon={icon} width={22} height={22} aria-hidden />
      <span className="rp-text-primary font-medium">{label}</span>
      <span className="rp-text-muted text-xs">{hint}</span>
    </button>
  )
}
