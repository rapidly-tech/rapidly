'use client'

/**
 * Bottom-sheet wrapper around ``PropertiesPanel`` for phone-width
 * viewports.
 *
 * Phase 26c hides the right-hand properties sidebar on phones so the
 * canvas gets full width. This sheet puts the same controls behind a
 * toolbar button — tap opens a slide-up modal, tap the backdrop or
 * Esc closes. One component, one render, no new state machine.
 *
 * Accessibility
 * -------------
 * ``role=""dialog""`` + ``aria-modal`` + ``aria-labelledby`` so screen
 * readers announce it as a modal. Focus moves to the close button on
 * open and restores to the previously-focused element on close —
 * matches ``ShortcutsOverlay`` (Phase 14b).
 */

import { useEffect, useRef } from 'react'

import type { ElementStore } from '@/utils/collab/element-store'
import type { SelectionState } from '@/utils/collab/selection'

import { PropertiesPanel } from './PropertiesPanel'

interface Props {
  open: boolean
  store: ElementStore
  selection: SelectionState
  onClose: () => void
}

export function MobilePropertiesSheet({
  open,
  store,
  selection,
  onClose,
}: Props) {
  const closeBtnRef = useRef<HTMLButtonElement | null>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!open) return
    previousFocusRef.current = document.activeElement as HTMLElement | null
    closeBtnRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      previousFocusRef.current?.focus?.()
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      role="presentation"
      onClick={onClose}
      className="fixed inset-0 z-40 flex items-end justify-center bg-slate-900/40 backdrop-blur-sm md:hidden"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="collab-mobile-properties-title"
        onClick={(e) => e.stopPropagation()}
        className="flex max-h-[75vh] w-full flex-col rounded-t-xl border-t border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-900"
      >
        {/* Grab-handle pill at the top — standard iOS / Material sheet
            affordance. Purely visual; swipe-to-close lands in a
            follow-up since it needs pointer-event wiring. */}
        <div className="flex justify-center pt-2">
          <span className="h-1.5 w-10 rounded-full bg-slate-300 dark:bg-slate-600" />
        </div>
        <div className="flex items-center justify-between px-4 py-2">
          <h2
            id="collab-mobile-properties-title"
            className="text-sm font-semibold text-slate-900 dark:text-slate-100"
          >
            Style
          </h2>
          <button
            ref={closeBtnRef}
            type="button"
            onClick={onClose}
            aria-label="Close style panel"
            className="rounded-md px-2 py-1 text-sm text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
          >
            ✕
          </button>
        </div>
        <div className="overflow-y-auto">
          <PropertiesPanel store={store} selection={selection} />
        </div>
      </div>
    </div>
  )
}
