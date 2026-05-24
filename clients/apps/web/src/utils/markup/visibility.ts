/**
 * Element visibility — show / hide elements without deleting them.
 *
 * The renderer + hit-test pass each gate on ``el.hidden``; this
 * module owns the write side so the outline panel + command
 * palette + keyboard shortcut all flip the same field through one
 * helper.
 */

import type { ElementStore } from './element-store'
import type { CollabElement } from './elements'

/** Set ``hidden`` on every element in ``ids``. The patch is sent
 *  through ``store.updateMany`` so remote peers see one
 *  transaction. ``hidden=false`` clears the flag (we write
 *  ``undefined`` so the JSON snapshot stays small — the renderer
 *  treats undefined and false the same). */
export function setHidden(
  store: ElementStore,
  ids: ReadonlySet<string>,
  hidden: boolean,
): void {
  if (ids.size === 0) return
  const patches: { id: string; patch: Record<string, unknown> }[] = []
  for (const id of ids) {
    if (!store.get(id)) continue
    patches.push({ id, patch: { hidden: hidden ? true : undefined } })
  }
  if (patches.length === 0) return
  store.updateMany(patches)
}

/** Toggle ``hidden`` on every element in ``ids``. When mixed
 *  (some hidden, some visible), the result is "all hidden" so the
 *  next toggle flips them all back in one step — matches the
 *  Figma / Sketch behaviour. */
export function toggleHidden(
  store: ElementStore,
  ids: ReadonlySet<string>,
): void {
  if (ids.size === 0) return
  let anyVisible = false
  for (const id of ids) {
    const el = store.get(id)
    if (el && !el.hidden) {
      anyVisible = true
      break
    }
  }
  setHidden(store, ids, anyVisible)
}

/** Convenience predicate. Returns ``true`` when the element is
 *  hidden — undefined and false are both visible per the field's
 *  doc comment. */
export function isHidden(el: CollabElement): boolean {
  return el.hidden === true
}
