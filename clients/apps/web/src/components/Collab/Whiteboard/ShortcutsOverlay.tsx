'use client'

/**
 * Keyboard-shortcut cheat sheet modal.
 *
 * Opens with **?** (Shift+/), closes on **Esc** or backdrop click.
 * The content comes straight from ``utils/collab/shortcuts.ts`` —
 * when a new shortcut lands in that module, it appears here for
 * free.
 *
 * Accessibility
 * -------------
 *  - ``role="dialog"`` + ``aria-modal`` + ``aria-labelledby`` so
 *    screen readers announce it as a modal.
 *  - Focus moves to the close button on open and restores to the
 *    previously-focused element on close (the toolbar button that
 *    opened it, typically).
 *  - Backdrop click and Escape both dismiss — matches native OS
 *    modal conventions.
 */

import { useEffect, useRef } from 'react'

import {
  SHORTCUT_CATEGORIES,
  formatKeys,
  type Shortcut,
} from '@/utils/collab/shortcuts'

interface Props {
  open: boolean
  onClose: () => void
}

export function ShortcutsOverlay({ open, onClose }: Props) {
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
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="collab-shortcuts-title"
        onClick={(e) => e.stopPropagation()}
        className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-lg border border-slate-200 bg-white p-6 shadow-xl dark:border-slate-700 dark:bg-slate-900"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2
            id="collab-shortcuts-title"
            className="text-lg font-semibold text-slate-900 dark:text-slate-100"
          >
            Keyboard shortcuts
          </h2>
          <button
            ref={closeBtnRef}
            type="button"
            onClick={onClose}
            aria-label="Close shortcuts overlay"
            className="rounded-md px-2 py-1 text-sm text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
          >
            ✕
          </button>
        </div>
        <div className="grid gap-6 md:grid-cols-2">
          {SHORTCUT_CATEGORIES.map((cat) => (
            <section key={cat.label}>
              <h3 className="mb-2 text-xs font-medium tracking-wide text-slate-500 uppercase dark:text-slate-400">
                {cat.label}
              </h3>
              <ul className="flex flex-col gap-1.5">
                {cat.entries.map((entry) => (
                  <Row key={entry.description} entry={entry} />
                ))}
              </ul>
            </section>
          ))}
        </div>
      </div>
    </div>
  )
}

function Row({ entry }: { entry: Shortcut }) {
  const keys = formatKeys(entry.keys)
  return (
    <li className="flex items-center justify-between gap-3 text-sm">
      <span className="text-slate-700 dark:text-slate-200">
        {entry.description}
      </span>
      <span className="flex items-center gap-1">
        {keys.map((k, i) => (
          <kbd
            key={`${k}-${i}`}
            className="inline-flex min-w-[1.5rem] justify-center rounded border border-slate-300 bg-slate-50 px-1.5 py-0.5 font-mono text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
          >
            {k}
          </kbd>
        ))}
      </span>
    </li>
  )
}
