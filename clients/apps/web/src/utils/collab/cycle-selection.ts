/**
 * Tab-cycle through every element on the scene in reading order
 * (top-down, then left-right of each element's centre). Mirrors
 * the order ``scene-outline.ts`` uses for root entries so the
 * Tab path and the outline panel agree.
 *
 * Usage:
 *   - Tab        → next  (``cycleNext``)
 *   - Shift+Tab  → prev  (``cyclePrev``)
 *
 * Both helpers take the current selection's first id as an anchor;
 * with no selection / a stale anchor they jump to the first
 * (Tab) or last (Shift+Tab) element on the scene. Hidden +
 * locked elements are skipped — keyboard nav shouldn't land on
 * something the user can't see or edit.
 */

import type { CollabElement } from './elements'

/** Pure reading-order sort. Top-down by centre Y, ties broken by
 *  left-right by centre X. Matches the ordering ``scene-outline``
 *  uses for root entries. */
function sortReadingOrder(elements: readonly CollabElement[]): CollabElement[] {
  return [...elements].sort((a, b) => {
    const ay = a.y + a.height / 2
    const by = b.y + b.height / 2
    if (ay !== by) return ay - by
    return a.x + a.width / 2 - (b.x + b.width / 2)
  })
}

function eligible(elements: readonly CollabElement[]): CollabElement[] {
  return elements.filter((el) => !el.hidden && !el.locked)
}

/** Return the id of the element after ``currentId`` in reading
 *  order. Wraps to the first element when ``currentId`` is the
 *  last (or no longer in the eligible list). Returns ``null``
 *  when there are no eligible elements at all. */
export function cycleNext(
  elements: readonly CollabElement[],
  currentId: string | null,
): string | null {
  const ordered = sortReadingOrder(eligible(elements))
  if (ordered.length === 0) return null
  if (!currentId) return ordered[0]!.id
  const idx = ordered.findIndex((el) => el.id === currentId)
  if (idx === -1) return ordered[0]!.id
  return ordered[(idx + 1) % ordered.length]!.id
}

/** Mirror of ``cycleNext`` going the other direction. */
export function cyclePrev(
  elements: readonly CollabElement[],
  currentId: string | null,
): string | null {
  const ordered = sortReadingOrder(eligible(elements))
  if (ordered.length === 0) return null
  if (!currentId) return ordered[ordered.length - 1]!.id
  const idx = ordered.findIndex((el) => el.id === currentId)
  if (idx === -1) return ordered[ordered.length - 1]!.id
  return ordered[(idx - 1 + ordered.length) % ordered.length]!.id
}
