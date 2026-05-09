'use client'

/**
 * Command palette modal — Cmd+Shift+P opens a searchable launcher for
 * every action the demo exposes.
 *
 * Keyboard model
 * --------------
 *   - Typing into the input filters commands via ``matchCommands``.
 *   - ArrowUp / ArrowDown move the highlight; wraps at both ends.
 *   - Enter runs the highlighted command and closes.
 *   - Esc closes without running.
 *
 * Accessibility
 * -------------
 * ``role="dialog"`` + ``aria-modal`` + the list is ``role="listbox"``
 * with ``aria-activedescendant`` pointing at the current highlight so
 * screen readers announce the selected item as the user arrow-keys.
 */

import { useEffect, useMemo, useRef, useState } from 'react'

import { matchCommands, type Command } from '@/utils/collab/command-palette'
import { formatKeys } from '@/utils/collab/shortcuts'

interface Props {
  open: boolean
  commands: readonly Command[]
  onClose: () => void
}

export function CommandPalette({ open, commands, onClose }: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)
  const [query, setQuery] = useState('')
  const [highlight, setHighlight] = useState(0)

  // Reset query + highlight each time the palette opens so it feels
  // fresh and stateless to the user.
  useEffect(() => {
    if (!open) return
    previousFocusRef.current = document.activeElement as HTMLElement | null
    setQuery('')
    setHighlight(0)
    // Focus on the input so the user can start typing immediately.
    queueMicrotask(() => inputRef.current?.focus())
    return () => {
      previousFocusRef.current?.focus?.()
    }
  }, [open])

  const matches = useMemo(
    () => matchCommands(query, commands),
    [query, commands],
  )

  // Clamp highlight to the new list bounds whenever matches change.
  useEffect(() => {
    if (highlight >= matches.length) setHighlight(0)
  }, [matches.length, highlight])

  if (!open) return null

  const runHighlighted = (): void => {
    const cmd = matches[highlight]
    if (!cmd) return
    onClose()
    void cmd.run()
  }

  const onKey = (e: React.KeyboardEvent<HTMLDivElement>): void => {
    if (e.key === 'Escape') {
      e.preventDefault()
      onClose()
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlight((i) => (matches.length === 0 ? 0 : (i + 1) % matches.length))
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlight((i) =>
        matches.length === 0 ? 0 : (i - 1 + matches.length) % matches.length,
      )
      return
    }
    if (e.key === 'Enter') {
      e.preventDefault()
      runHighlighted()
    }
  }

  return (
    <div
      role="presentation"
      onClick={onClose}
      onKeyDown={onKey}
      className="fixed inset-0 z-50 flex items-start justify-center bg-slate-900/40 pt-24 backdrop-blur-sm"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg overflow-hidden rounded-lg border border-slate-200 bg-white shadow-xl dark:border-slate-700 dark:bg-slate-900"
      >
        <input
          ref={inputRef}
          type="text"
          placeholder="Run a command…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full border-b border-slate-200 bg-transparent px-4 py-3 text-sm text-slate-900 outline-none dark:border-slate-700 dark:text-slate-100"
          aria-autocomplete="list"
          aria-controls="collab-command-list"
          aria-activedescendant={
            matches[highlight]
              ? `collab-command-${matches[highlight].id}`
              : undefined
          }
        />
        <ul
          id="collab-command-list"
          role="listbox"
          className="max-h-[60vh] overflow-y-auto py-1"
        >
          {matches.length === 0 ? (
            <li className="px-4 py-3 text-sm text-slate-500 dark:text-slate-400">
              No matches
            </li>
          ) : (
            matches.map((cmd, i) => (
              <li
                key={cmd.id}
                id={`collab-command-${cmd.id}`}
                role="option"
                aria-selected={i === highlight}
                onMouseEnter={() => setHighlight(i)}
                onClick={() => {
                  setHighlight(i)
                  runHighlighted()
                }}
                className={
                  'flex cursor-pointer items-center justify-between px-4 py-2 text-sm ' +
                  (i === highlight
                    ? 'bg-indigo-50 text-indigo-900 dark:bg-indigo-950/40 dark:text-indigo-100'
                    : 'text-slate-700 dark:text-slate-200')
                }
              >
                <span className="flex items-center gap-2">
                  {cmd.category ? (
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                      {cmd.category}
                    </span>
                  ) : null}
                  <span>{cmd.label}</span>
                </span>
                {cmd.shortcut ? (
                  <span className="flex items-center gap-1">
                    {formatKeys(cmd.shortcut).map((k, j) => (
                      <kbd
                        key={`${k}-${j}`}
                        className="inline-flex min-w-[1.25rem] justify-center rounded border border-slate-200 bg-slate-50 px-1 py-0.5 font-mono text-[10px] text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
                      >
                        {k}
                      </kbd>
                    ))}
                  </span>
                ) : null}
              </li>
            ))
          )}
        </ul>
      </div>
    </div>
  )
}
