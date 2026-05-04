/**
 * Element locking for the Collab v2 whiteboard.
 *
 * ``BaseElement.locked`` already carries the boolean; this module owns
 * the atomic ops and the invariants every write-path must honour:
 *
 *  - A locked element is **still selectable** — users need to click
 *    one to unlock it. We don't block selection.
 *  - A locked element **cannot move, resize, or be deleted** by the
 *    local user. Remote peers with their own unlock can still edit,
 *    exactly like any Yjs field — lock is advisory, not crypto.
 *  - Style / colour edits **still apply** to a locked element when
 *    explicitly selected. "Locked" reads as "pinned in place" rather
 *    than "frozen".
 *
 * The tools + demo keyboard handlers call ``filterUnlocked`` on their
 * target set before mutating so the invariants above hold without a
 * per-tool ``if (locked) continue`` sprinkle.
 */

import type { ElementStore } from './element-store'
import type { CollabElement } from './elements'

export function isLocked(el: { locked?: boolean }): boolean {
  return el.locked === true
}

/** Flip the ``locked`` flag on every selected element. Each element
 *  toggles independently — if the selection mixes locked + unlocked,
 *  they flip state individually. Use ``setLock`` when you need the
 *  whole selection to land in a specific state. */
export function toggleLock(
  store: ElementStore,
  selected: ReadonlySet<string>,
): boolean {
  if (selected.size === 0) return false
  const patches: { id: string; patch: { locked: boolean } }[] = []
  for (const id of selected) {
    const el = store.get(id)
    if (!el) continue
    patches.push({ id, patch: { locked: !isLocked(el) } })
  }
  if (patches.length === 0) return false
  store.updateMany(patches)
  return true
}

/** Force-set every selected element's ``locked`` flag. Skips elements
 *  that already match the target state so the transaction only writes
 *  real changes — keeps remote peers quiet when there's nothing to
 *  actually broadcast. */
export function setLock(
  store: ElementStore,
  selected: ReadonlySet<string>,
  locked: boolean,
): boolean {
  if (selected.size === 0) return false
  const patches: { id: string; patch: { locked: boolean } }[] = []
  for (const id of selected) {
    const el = store.get(id)
    if (!el) continue
    if (isLocked(el) === locked) continue
    patches.push({ id, patch: { locked } })
  }
  if (patches.length === 0) return false
  store.updateMany(patches)
  return true
}

/** Return the subset of ``ids`` whose backing element is not locked.
 *  Ids missing from the store fall through silently (matches every
 *  other ""skip unknown"" site in the codebase). Tools call this on
 *  delete / move / resize paths so locks are honoured without a
 *  per-call-site check. */
export function filterUnlocked(
  store: ElementStore,
  ids: ReadonlySet<string>,
): Set<string> {
  const out = new Set<string>()
  for (const id of ids) {
    const el = store.get(id)
    if (el && !isLocked(el)) out.add(id)
  }
  return out
}

/** True when *every* listed element is locked. Useful for the UI
 *  (toolbar toggle shows ""unlock"" vs ""lock"" based on whether the
 *  current selection is fully locked). */
export function allLocked(elements: readonly CollabElement[]): boolean {
  if (elements.length === 0) return false
  for (const el of elements) {
    if (!isLocked(el)) return false
  }
  return true
}
