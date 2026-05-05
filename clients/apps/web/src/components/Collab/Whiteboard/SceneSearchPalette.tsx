'use client'

/**
 * Scene-search palette — Cmd+F opens a searchable list of every
 * text-bearing element on the whiteboard. Selecting a hit pans the
 * viewport to that element and selects it.
 *
 * Mirrors the Command palette's keyboard model:
 *   - Typing into the input filters via ``searchScene``.
 *   - ArrowUp / ArrowDown move the highlight; wraps at both ends.
 *   - Enter focuses the highlighted hit and closes.
 *   - Esc closes without selecting.
 */

import { useEffect, useMemo, useRef, useState } from 'react'

import type { CollabElement } from '@/utils/collab/elements'
import { searchScene, type SearchHit } from '@/utils/collab/scene-search'

interface Props {
  open: boolean
  elements: CollabElement[]
  onPick: (hit: SearchHit) => void
  onClose: () => void
}

export function SceneSearchPalette({ open, elements, onPick, onClose }: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)
  const [query, setQuery] = useState('')
  const [highlight, setHighlight] = useState(0)

  useEffect(() => {
    if (!open) return
    previousFocusRef.current = document.activeElement as HTMLElement | null
    setQuery('')
    setHighlight(0)
    queueMicrotask(() => inputRef.current?.focus())
    return () => {
      previousFocusRef.current?.focus?.()
    }
  }, [open])

  const hits = useMemo(() => searchScene(elements, query), [elements, query])

  useEffect(() => {
    if (highlight >= hits.length) setHighlight(0)
  }, [hits.length, highlight])

  if (!open) return null

  const pickHighlighted = (): void => {
    const hit = hits[highlight]
    if (!hit) return
    onClose()
    onPick(hit)
  }

  const onKey = (e: React.KeyboardEvent<HTMLDivElement>): void => {
    if (e.key === 'Escape') {
      e.preventDefault()
      onClose()
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlight((i) => (hits.length === 0 ? 0 : (i + 1) % hits.length))
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlight((i) =>
        hits.length === 0 ? 0 : (i - 1 + hits.length) % hits.length,
      )
      return
    }
    if (e.key === 'Enter') {
      e.preventDefault()
      pickHighlighted()
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
        aria-label="Find on whiteboard"
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg overflow-hidden rounded-lg border border-slate-200 bg-white shadow-xl dark:border-slate-700 dark:bg-slate-900"
      >
        <input
          ref={inputRef}
          type="text"
          placeholder="Find on whiteboard…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full border-b border-slate-200 bg-transparent px-4 py-3 text-sm text-slate-900 outline-none dark:border-slate-700 dark:text-slate-100"
          aria-autocomplete="list"
          aria-controls="collab-search-list"
          aria-activedescendant={
            hits[highlight]
              ? `collab-search-${hits[highlight].elementId}`
              : undefined
          }
        />
        <ul
          id="collab-search-list"
          role="listbox"
          className="max-h-[60vh] overflow-y-auto py-1"
        >
          {query.trim().length === 0 ? (
            <li className="px-4 py-3 text-sm text-slate-500 dark:text-slate-400">
              Type to search element labels, sticky notes, frames, and embeds.
            </li>
          ) : hits.length === 0 ? (
            <li className="px-4 py-3 text-sm text-slate-500 dark:text-slate-400">
              No matches
            </li>
          ) : (
            hits.map((hit, i) => (
              <li
                key={hit.elementId}
                id={`collab-search-${hit.elementId}`}
                role="option"
                aria-selected={i === highlight}
                onMouseEnter={() => setHighlight(i)}
                onClick={() => {
                  setHighlight(i)
                  pickHighlighted()
                }}
                className={
                  'flex cursor-pointer items-center gap-2 px-4 py-2 text-sm ' +
                  (i === highlight
                    ? 'bg-indigo-50 text-indigo-900 dark:bg-indigo-950/40 dark:text-indigo-100'
                    : 'text-slate-700 dark:text-slate-200')
                }
              >
                <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                  {hit.kind}
                </span>
                <span className="truncate">{hit.snippet}</span>
              </li>
            ))
          )}
        </ul>
      </div>
    </div>
  )
}
