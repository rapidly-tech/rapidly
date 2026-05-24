/**
 * Find-next / find-previous — keyboard navigation through the
 * results of the most recent scene-search query, without
 * re-opening the palette.
 *
 * The scene-search palette closes after picking a hit (cleaner UX
 * than a sticky modal). To support iterative "step through the
 * matches" navigation we cache the last query + cursor position
 * here, run the search again on demand against the live element
 * list, and return the next / previous hit.
 *
 * Why re-run the search rather than caching the hit list itself:
 * elements move / rename / get deleted between searches; pinning
 * to ids that may have moved (or no longer exist) would surprise
 * the user. Re-running gives the freshest result set with O(N)
 * cost — fine for whiteboards in the thousands-of-elements range.
 */

import type { CollabElement } from './elements'
import { searchScene, type SearchHit } from './scene-search'

interface State {
  query: string
  /** Id of the hit the user picked (or stepped to) most recently.
   *  ``next`` finds the hit *after* this id in the result list;
   *  ``previous`` finds the one before. Cleared when the query
   *  changes. */
  lastPickedId: string | null
}

let state: State = { query: '', lastPickedId: null }

/** Record the search query + the hit the user just picked. The
 *  search palette calls this whenever the user picks a hit so
 *  ``findNext`` / ``findPrevious`` can resume from there. */
export function recordSearchPick(query: string, pickedId: string): void {
  state = { query: query.trim(), lastPickedId: pickedId }
}

/** Return the hit *after* the last-picked one in the cached
 *  query's result list. Wraps to the first when the cursor is on
 *  the last hit. Returns ``null`` when there's no cached query
 *  or the query produces no hits (the keyboard handler can show
 *  a "nothing to find" hint). */
export function findNext(elements: CollabElement[]): SearchHit | null {
  return step(elements, +1)
}

/** Return the hit *before* the last-picked one. Wraps to the last
 *  when the cursor is on the first. */
export function findPrevious(elements: CollabElement[]): SearchHit | null {
  return step(elements, -1)
}

/** Read-only view of the active query. Used by the keyboard
 *  handler to decide whether the find-next path should fire or
 *  fall through (Cmd+G with no prior search is a no-op rather
 *  than an error). */
export function hasActiveSearch(): boolean {
  return state.query.length > 0
}

function step(elements: CollabElement[], direction: 1 | -1): SearchHit | null {
  if (state.query.length === 0) return null
  const hits = searchScene(elements, state.query)
  if (hits.length === 0) return null
  const idx = state.lastPickedId
    ? hits.findIndex((h) => h.elementId === state.lastPickedId)
    : -1
  let nextIdx: number
  if (idx === -1) {
    // Cursor moved off the result set (element deleted, query
    // changed silently) → restart from the appropriate end.
    nextIdx = direction === 1 ? 0 : hits.length - 1
  } else {
    nextIdx = (idx + direction + hits.length) % hits.length
  }
  const next = hits[nextIdx]!
  state = { query: state.query, lastPickedId: next.elementId }
  return next
}

/** Test seam — clears the cached query + cursor. Production code
 *  doesn't call this. */
export function _resetFindStateForTests(): void {
  state = { query: '', lastPickedId: null }
}
