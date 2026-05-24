/**
 * Recent-colours palette — keeps the last N stroke / fill colours
 * the user picked so they can re-apply a brand colour without
 * re-typing the hex.
 *
 * Storage model
 * -------------
 *   - In-memory LRU array (most-recent first).
 *   - Mirrored to ``localStorage`` under a single key when
 *     available, so the row survives page reloads.
 *   - ``transparent`` is excluded — it's already a preset and
 *     would dominate the LRU otherwise (every empty-fill click
 *     would push it).
 *   - Same colour picked twice in a row is deduped (moved to
 *     front rather than added a second time).
 *
 * The module exposes a tiny pub/sub so the swatches row repaints
 * the moment a new colour lands in the LRU. The host wires
 * ``subscribeRecentColors`` to a setState in the panel.
 */

import { normaliseHex } from './hex-color'

export const RECENT_COLORS_LIMIT = 10
const STORAGE_KEY = 'rapidly:collab:recent-colors:v1'

type Listener = (colors: readonly string[]) => void

let cache: string[] | null = null
const listeners = new Set<Listener>()

function read(): string[] {
  if (cache !== null) return cache
  cache = []
  if (typeof localStorage === 'undefined') return cache
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return cache
    const parsed = JSON.parse(raw) as unknown
    if (Array.isArray(parsed)) {
      cache = parsed
        .filter((v): v is string => typeof v === 'string')
        .slice(0, RECENT_COLORS_LIMIT)
    }
  } catch {
    // Corrupt localStorage entry — start clean rather than throw.
    cache = []
  }
  return cache
}

function write(next: string[]): void {
  cache = next
  if (typeof localStorage !== 'undefined') {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    } catch {
      // Quota or privacy mode — keep the in-memory cache so the row
      // still updates within the session.
    }
  }
  for (const fn of listeners) fn(next)
}

/** Read the current recent-colours array (most-recent first). */
export function getRecentColors(): readonly string[] {
  return read()
}

/** Push a colour to the front of the LRU. Skips ``transparent``,
 *  invalid hex strings, and already-front entries (which would
 *  produce a redundant rewrite + listener fire). */
export function addRecentColor(color: string): void {
  if (!color || color === 'transparent') return
  const canonical = normaliseHex(color) ?? color
  const current = read()
  if (current[0] === canonical) return
  const next = [canonical, ...current.filter((c) => c !== canonical)].slice(
    0,
    RECENT_COLORS_LIMIT,
  )
  write(next)
}

/** Subscribe to LRU updates. Returns an unsubscribe handle. The
 *  listener fires synchronously on every ``addRecentColor`` /
 *  ``clearRecentColors`` call. */
export function subscribeRecentColors(fn: Listener): () => void {
  listeners.add(fn)
  return () => {
    listeners.delete(fn)
  }
}

/** Wipe the LRU. Used by the test seam below + the future
 *  "Clear recent colours" command-palette entry if we add one. */
export function clearRecentColors(): void {
  write([])
}

/** Test seam — drops the in-memory cache so the next ``read`` re-
 *  hydrates from storage (or starts empty when storage isn't
 *  available). Production code never calls this. */
export function _resetRecentColorsForTests(): void {
  cache = null
  listeners.clear()
}
