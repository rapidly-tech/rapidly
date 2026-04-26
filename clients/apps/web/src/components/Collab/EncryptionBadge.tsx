'use client'

/**
 * Small pill badge showing the room's aggregate encryption state.
 * Reads from ``useCollabRoom().encryption``; the aggregator rules
 * live in ``utils/collab/encryption-state.ts``.
 *
 *   e2ee       — emerald "End-to-end encrypted"
 *   pending    — slate "Securing…"
 *   mixed      — amber "Mixed encryption" (warn, should be transient)
 *   plaintext  — amber "Not encrypted" (should not happen when the
 *                E2EE flag is default-on; surfaces if a deployment
 *                has opted out).
 *   solo       — hidden (no peers yet → nothing to assert)
 */

import { Icon } from '@iconify/react'

import type { RoomEncryptionState } from '@/utils/collab/encryption-state'

interface Props {
  state: RoomEncryptionState
}

export function EncryptionBadge({ state }: Props) {
  if (state === 'solo') return null

  const { icon, label, classes } = descriptorFor(state)
  return (
    <span
      className={
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ' +
        classes
      }
      aria-label={`Session encryption state: ${label}`}
    >
      <Icon icon={icon} width={14} height={14} aria-hidden />
      {label}
    </span>
  )
}

function descriptorFor(state: Exclude<RoomEncryptionState, 'solo'>): {
  icon: string
  label: string
  classes: string
} {
  switch (state) {
    case 'e2ee':
      return {
        icon: 'lucide:shield-check',
        label: 'End-to-end encrypted',
        classes:
          'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200',
      }
    case 'pending':
      return {
        icon: 'lucide:loader',
        label: 'Securing…',
        classes:
          'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200',
      }
    case 'mixed':
      return {
        icon: 'lucide:shield-alert',
        label: 'Mixed encryption',
        classes:
          'bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-100',
      }
    case 'plaintext':
      return {
        icon: 'lucide:shield-off',
        label: 'Not encrypted',
        classes:
          'bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-100',
      }
  }
}
