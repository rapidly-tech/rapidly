/**
 * Shared list-control primitives for the Agents chamber.
 *
 * Five list pages (workflows, datasets, eval-runs, credentials,
 * vector-collections) all carry the same shape:
 *   workspace switcher  →  search  →  per-page filter chips  →
 *   results  →  Prev / Next pagination
 *
 * Each page assembles its own filter chips (status, publish
 * state, outcome) — those stay local because the per-page
 * options + state shape vary. The four primitives below
 * (`Pagination`, `SearchInput`, `EmptySearch`, `WorkspaceSwitcher`)
 * are identical across the five pages and live here so a single
 * accessibility/styling fix doesn't fan out to five files.
 */
'use client'

import type { ReactNode } from 'react'

// ── Pagination (Prev / Next + counter caption) ────────────────

export interface PaginationProps {
  page: number
  pages: number
  total: number
  onPageChange: (next: number) => void
}

/**
 * Prev / Next pagination with a "Page N of M · T total" caption.
 * Hides itself when there's only one page so list pages without
 * overflow don't render an empty bar.
 */
export function Pagination({
  page,
  pages,
  total,
  onPageChange,
}: PaginationProps) {
  if (pages <= 1) return null
  return (
    <div className="flex items-center justify-between gap-3 text-xs text-slate-500 dark:text-slate-400">
      <span>
        Page <span className="font-mono">{page}</span> of{' '}
        <span className="font-mono">{pages}</span> ·{' '}
        <span className="font-mono">{total}</span> total
      </span>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page <= 1}
          className="rounded-md border border-slate-200 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          ← Prev
        </button>
        <button
          type="button"
          onClick={() => onPageChange(Math.min(pages, page + 1))}
          disabled={page >= pages}
          className="rounded-md border border-slate-200 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          Next →
        </button>
      </div>
    </div>
  )
}

// ── Search input ──────────────────────────────────────────────

export interface SearchInputProps {
  value: string
  onChange: (next: string) => void
  /** Placeholder text inside the input. */
  placeholder: string
  /** Visible label above the input. Defaults to "Search". */
  label?: string
}

export function SearchInput({
  value,
  onChange,
  placeholder,
  label = 'Search',
}: SearchInputProps) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs tracking-wide text-slate-400 uppercase dark:text-slate-500">
        {label}
      </label>
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full max-w-md rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
      />
    </div>
  )
}

// ── Empty-search banner ───────────────────────────────────────

export interface EmptySearchProps {
  /** The trimmed search term the operator typed. */
  query: string
  /** What kind of thing the operator was searching for, plural. */
  noun: string
}

/**
 * Banner rendered when the active search filter matches zero
 * rows. Quotes the typed term inside a `<code>` so it reads
 * unambiguously in plain text too.
 */
export function EmptySearch({ query, noun }: EmptySearchProps) {
  return (
    <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-400">
      No {noun} match{' '}
      <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono dark:bg-slate-800">
        {query}
      </code>
      .
    </div>
  )
}

// ── Workspace switcher ────────────────────────────────────────

export interface WorkspaceSwitcherProps {
  workspaces: { id: string; name: string }[]
  activeId: string | null
  onChange: (id: string) => void
}

/**
 * Native `<select>` that lets multi-workspace operators flip
 * between workspaces. Hidden entirely when there's only one
 * workspace — single-workspace operators get no chrome.
 */
export function WorkspaceSwitcher({
  workspaces,
  activeId,
  onChange,
}: WorkspaceSwitcherProps) {
  if (workspaces.length <= 1) return null
  return (
    <div className="flex flex-col gap-2">
      <label className="text-xs tracking-wide text-slate-400 uppercase dark:text-slate-500">
        Workspace
      </label>
      <select
        value={activeId ?? ''}
        onChange={(e) => onChange(e.target.value)}
        className="w-full max-w-md rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
      >
        {workspaces.map((w) => (
          <option key={w.id} value={w.id}>
            {w.name}
          </option>
        ))}
      </select>
    </div>
  )
}

// ── Pass-through helper for tests/storybooks ──────────────────
// (Re-export ReactNode so callers don't have to import twice.)
export type { ReactNode }
