'use client'

/**
 * Template-library picker.
 *
 * Lists every template the user has saved into the local library
 * (``utils/collab/library.ts``) and lets them insert one into the
 * current scene at viewport centre, or delete one they no longer
 * want. Insert calls back via ``onInsert`` so the parent can place
 * the template at a sensible target without this component holding
 * a renderer reference.
 *
 * Local-only: there's no public hosting and no cross-device sync.
 * Per the clean-room policy.
 */

import { useEffect, useRef, useState } from 'react'

import {
  deleteTemplate,
  listTemplates,
  type LibraryTemplate,
} from '@/utils/collab/library'

interface Props {
  open: boolean
  onClose: () => void
  /** Called with the template the user picked. The parent inserts
   *  via ``insertTemplate`` from the library module so this dialog
   *  doesn't need a store / renderer reference. */
  onInsert: (template: LibraryTemplate) => void
}

export function LibraryDialog({ open, onClose, onInsert }: Props) {
  const closeBtn = useRef<HTMLButtonElement | null>(null)
  // ``revision`` is a dummy state we bump to force a re-render after
  // a delete; the listTemplates() read is cheap enough to do on
  // every render (synchronous localStorage read, < 1ms).
  const [, tick] = useState(0)
  const templates = listTemplates()
  const previousFocus = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!open) return
    previousFocus.current = document.activeElement as HTMLElement | null
    closeBtn.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      previousFocus.current?.focus?.()
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
        aria-labelledby="collab-library-title"
        onClick={(e) => e.stopPropagation()}
        className="flex max-h-[80vh] w-full max-w-lg flex-col gap-4 overflow-hidden rounded-lg border border-slate-200 bg-white p-6 shadow-xl dark:border-slate-700 dark:bg-slate-900"
      >
        <div className="flex items-center justify-between">
          <h2
            id="collab-library-title"
            className="text-lg font-semibold text-slate-900 dark:text-slate-100"
          >
            Template library
          </h2>
          <button
            ref={closeBtn}
            type="button"
            onClick={onClose}
            aria-label="Close library"
            className="rounded-md px-2 py-1 text-sm text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
          >
            ✕
          </button>
        </div>

        {templates.length === 0 ? (
          <p className="rp-text-secondary py-6 text-center text-sm">
            No templates saved yet. Select some elements and run{' '}
            <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-slate-800">
              Save selection as template…
            </code>{' '}
            from the command palette.
          </p>
        ) : (
          <ul className="-mx-2 flex flex-col gap-1 overflow-y-auto">
            {templates.map((t) => (
              <li
                key={t.id}
                className="flex items-center gap-3 rounded-md px-2 py-2 hover:bg-slate-50 dark:hover:bg-slate-800"
              >
                <button
                  type="button"
                  className="flex flex-1 items-center gap-3 text-left"
                  onClick={() => {
                    onInsert(t)
                    onClose()
                  }}
                >
                  <span className="rp-text-primary truncate font-medium">
                    {t.name}
                  </span>
                  <span className="rp-text-muted ml-auto font-mono text-xs">
                    {Math.round(t.width)}×{Math.round(t.height)}
                    {' · '}
                    {t.elements.length} el
                  </span>
                </button>
                <button
                  type="button"
                  aria-label={`Delete template ${t.name}`}
                  title="Delete"
                  onClick={() => {
                    deleteTemplate(t.id)
                    tick((n) => n + 1)
                  }}
                  className="rounded-md px-2 py-1 text-xs text-slate-500 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/40"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
