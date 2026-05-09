/**
 * View-mode predicates for the Collab v2 whiteboard.
 *
 * "View mode" turns the editor into a read-only viewer: the user can
 * pan, zoom, follow a peer, and click hyperlinks, but cannot mutate
 * the scene. Used for share links where the recipient should observe
 * but not modify.
 *
 * Pure module — no React, no canvas. Two predicates:
 *
 *  - ``isViewModeShortcutAllowed(eventLike)`` — the hotkey we'd
 *    normally service is read-only-safe? Returns ``true`` for a
 *    short whitelist (copy, undo if we surface it, view-only
 *    palette commands etc) and ``false`` for everything else.
 *  - ``isReadOnlyTool(toolId)`` — the tool can be active in view
 *    mode without risking a store write?
 *
 * Both are designed to fail closed: anything we haven't thought
 * about is denied so a forgotten path can't accidentally mutate.
 */

import type { ToolId } from './tools/types'

/** URL query parameter that toggles view-mode at mount time. The
 *  guest + host clients read it via ``isViewModeUrl`` so a recipient
 *  who pastes a ``?view=1`` link always lands in read-only mode. */
export const VIEW_MODE_URL_PARAM = 'view'

/** Parse a query string (or full URL) and decide whether view-mode
 *  should be on. Truthy values: ``1``, ``true``, ``yes``, ``on``.
 *  Anything else (or a missing param) returns false. */
export function isViewModeUrl(searchOrUrl: string): boolean {
  if (!searchOrUrl) return false
  // Strip any fragment first so a #key=... after a query string doesn't
  // get glued onto the last param value.
  const hashIdx = searchOrUrl.indexOf('#')
  const noFragment = hashIdx >= 0 ? searchOrUrl.slice(0, hashIdx) : searchOrUrl
  const search = noFragment.includes('?')
    ? noFragment.slice(noFragment.indexOf('?'))
    : noFragment
  const params = new URLSearchParams(
    search.startsWith('?') ? search.slice(1) : search,
  )
  const raw = params.get(VIEW_MODE_URL_PARAM)
  if (raw === null) return false
  const value = raw.trim().toLowerCase()
  return value === '1' || value === 'true' || value === 'yes' || value === 'on'
}

/** Append ``?view=1`` to a URL so the recipient lands in read-only
 *  mode. Preserves any existing query params; replaces the value when
 *  the key is already present. Pure — no DOM. */
export function withViewModeUrl(url: string): string {
  // Split off the fragment (E2EE invite keys) so we don't disturb it.
  const hashIdx = url.indexOf('#')
  const head = hashIdx >= 0 ? url.slice(0, hashIdx) : url
  const tail = hashIdx >= 0 ? url.slice(hashIdx) : ''
  const qIdx = head.indexOf('?')
  const base = qIdx >= 0 ? head.slice(0, qIdx) : head
  const search = qIdx >= 0 ? head.slice(qIdx + 1) : ''
  const params = new URLSearchParams(search)
  params.set(VIEW_MODE_URL_PARAM, '1')
  return `${base}?${params.toString()}${tail}`
}

/** Subset of KeyboardEvent the predicate consults. The full event isn't
 *  passed so callers (and tests) can use a plain object literal. */
export interface ShortcutEventLike {
  readonly key: string
  readonly metaKey?: boolean
  readonly ctrlKey?: boolean
  readonly shiftKey?: boolean
  readonly altKey?: boolean
}

/** Tools that don't mutate the store. Pan/select/eraser are the
 *  obvious split-line: the first two are read-only, the rest write. */
const READ_ONLY_TOOLS: ReadonlySet<ToolId> = new Set(['hand', 'select'])

export function isReadOnlyTool(id: ToolId): boolean {
  return READ_ONLY_TOOLS.has(id)
}

/** Whether a keyboard shortcut should fire in view mode. Whitelist
 *  approach — anything not explicitly allowed is denied. */
export function isViewModeShortcutAllowed(e: ShortcutEventLike): boolean {
  const mod = !!(e.metaKey || e.ctrlKey)
  const k = e.key.toLowerCase()

  // Always-safe (no modifiers): tool-activation for read-only tools
  // (h / v) and the help / palette hotkeys.
  if (!mod && (k === 'h' || k === 'v')) return true
  if (!mod && k === 'escape') return true
  if (!mod && k === '?') return true

  // Cmd/Ctrl+Shift+P — open the palette. Palette items themselves
  // are individually allowed/denied by the palette filter.
  if (mod && e.shiftKey && k === 'p') return true

  // Cmd/Ctrl+C — copy (read-only).
  if (mod && !e.shiftKey && k === 'c') return true

  // Everything else (delete, cmd+v, cmd+x, cmd+d, cmd+g, cmd+z,
  // cmd+y, cmd+k, cmd+l, cmd+], cmd+[) is a mutation. Denied.
  return false
}

/** Filter palette commands by id. Read-only-safe ids start with one of
 *  the prefixes returned by ``readOnlyPaletteIdPrefixes``; everything
 *  else is suppressed when view mode is on. */
const READ_ONLY_PALETTE_PREFIXES: readonly string[] = [
  'view.', // zoom-to-fit, zoom-to-selection, toggle grid (visual-only), present
  'export.', // png / json / svg are all reads
  'help.', // shortcuts dialog
  'tool.hand', // pan
  'tool.select', // selection state only
]

export function readOnlyPaletteIdPrefixes(): readonly string[] {
  return READ_ONLY_PALETTE_PREFIXES
}

export function isReadOnlyPaletteCommand(id: string): boolean {
  return READ_ONLY_PALETTE_PREFIXES.some((p) => id === p || id.startsWith(p))
}
