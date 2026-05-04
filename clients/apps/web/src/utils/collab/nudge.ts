/**
 * Keyboard-arrow nudging for the Collab v2 whiteboard.
 *
 * Translates every selected (unlocked) element by ``(dx, dy)`` world
 * units in a single Yjs transaction so the whole batch lands on remote
 * peers as one frame and counts as one undo step. Bound-arrow endpoints
 * follow their target via the same mechanism the select tool uses
 * after a drag-move.
 *
 * Locked elements are filtered out so a nudge with a mixed selection
 * doesn t leave the locked elements behind silently — same contract as
 * Delete + drag-move.
 *
 * Pure module — no React, no canvas. The whiteboard's keydown handler
 * decides the (dx, dy) per ArrowKey + modifier and calls into here.
 */

import { collectBoundArrowPatches } from './arrow-bindings'
import type { ElementStore } from './element-store'
import { isLocked } from './locks'

/** Default world-units per arrow keystroke. Excalidraw + Figma both
 *  use 1 world-unit so a tap is precise; Shift bumps to 10 for fast
 *  travel. */
export const DEFAULT_NUDGE_STEP = 1
export const DEFAULT_NUDGE_LARGE_STEP = 10

/** Translate every selected unlocked element by ``(dx, dy)``. Returns
 *  the count of elements actually moved (excludes locked ones). No-op
 *  on empty selection or zero delta. */
export function nudge(
  store: ElementStore,
  selected: ReadonlySet<string>,
  dx: number,
  dy: number,
): number {
  if (selected.size === 0) return 0
  if (dx === 0 && dy === 0) return 0

  const patches: { id: string; patch: { x: number; y: number } }[] = []
  for (const id of selected) {
    const el = store.get(id)
    if (!el || isLocked(el)) continue
    patches.push({ id, patch: { x: el.x + dx, y: el.y + dy } })
  }
  if (patches.length === 0) return 0

  store.transact(() => {
    store.updateMany(patches)
    const changed = new Set<string>()
    for (const p of patches) changed.add(p.id)
    const arrowPatches = collectBoundArrowPatches(store.list(), changed)
    if (arrowPatches.length > 0) store.updateMany(arrowPatches)
  })
  return patches.length
}

/** Resolve an Arrow keypress to a world-space delta. Returns ``null``
 *  for any non-arrow key so callers can chain more handlers. */
export function deltaFromArrowKey(
  key: string,
  shift: boolean,
  step: number = DEFAULT_NUDGE_STEP,
  largeStep: number = DEFAULT_NUDGE_LARGE_STEP,
): { dx: number; dy: number } | null {
  const s = shift ? largeStep : step
  switch (key) {
    case 'ArrowLeft':
      return { dx: -s, dy: 0 }
    case 'ArrowRight':
      return { dx: s, dy: 0 }
    case 'ArrowUp':
      return { dx: 0, dy: -s }
    case 'ArrowDown':
      return { dx: 0, dy: s }
    default:
      return null
  }
}
