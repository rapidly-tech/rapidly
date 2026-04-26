/**
 * z-order actions for the Collab v2 whiteboard.
 *
 * Four standard operations that reshuffle selected elements relative
 * to the rest of the scene, matching Excalidraw / Figma conventions:
 *
 *  - ``bringToFront``  — selected go to the top of the paint order
 *  - ``sendToBack``    — selected go to the bottom
 *  - ``bringForward``  — each selected leapfrogs the next non-selected
 *                        element above it (one step up)
 *  - ``sendBackward``  — each selected leapfrogs the next non-selected
 *                        element below it (one step down)
 *
 * All four go through ``store.updateMany`` so remote peers see one
 * atomic frame. zIndex is renormalised to contiguous 0..N-1 ints
 * after each operation so the z-index space doesn't grow unbounded
 * over a long session.
 */

import type { ElementStore } from './element-store'

type Action = 'front' | 'back' | 'forward' | 'backward'

/** Compute the new order of ids given the current store list + the
 *  action. Pure function — tests exercise this directly. */
export function reorderedIds(
  currentOrder: readonly string[],
  selected: ReadonlySet<string>,
  action: Action,
): string[] {
  if (selected.size === 0) return [...currentOrder]

  const sel = currentOrder.filter((id) => selected.has(id))
  const rest = currentOrder.filter((id) => !selected.has(id))

  if (action === 'front') return [...rest, ...sel]
  if (action === 'back') return [...sel, ...rest]

  // forward / backward work element-by-element.
  const out = [...currentOrder]
  if (action === 'forward') {
    // Walk high→low so successive swaps don't cascade a selected
    // element past the group it would otherwise leapfrog.
    for (let i = out.length - 2; i >= 0; i--) {
      if (selected.has(out[i]) && !selected.has(out[i + 1])) {
        ;[out[i], out[i + 1]] = [out[i + 1], out[i]]
      }
    }
    return out
  }
  // backward — symmetric walk low→high.
  for (let i = 1; i < out.length; i++) {
    if (selected.has(out[i]) && !selected.has(out[i - 1])) {
      ;[out[i], out[i - 1]] = [out[i - 1], out[i]]
    }
  }
  return out
}

function applyReorder(
  store: ElementStore,
  selected: ReadonlySet<string>,
  action: Action,
): void {
  if (selected.size === 0) return
  const order = store.list().map((el) => el.id)
  const next = reorderedIds(order, selected, action)
  if (orderEquals(order, next)) return
  const patches: { id: string; patch: { zIndex: number } }[] = next.map(
    (id, i) => ({ id, patch: { zIndex: i } }),
  )
  store.updateMany(patches)
}

export function bringToFront(
  store: ElementStore,
  selected: ReadonlySet<string>,
): void {
  applyReorder(store, selected, 'front')
}

export function sendToBack(
  store: ElementStore,
  selected: ReadonlySet<string>,
): void {
  applyReorder(store, selected, 'back')
}

export function bringForward(
  store: ElementStore,
  selected: ReadonlySet<string>,
): void {
  applyReorder(store, selected, 'forward')
}

export function sendBackward(
  store: ElementStore,
  selected: ReadonlySet<string>,
): void {
  applyReorder(store, selected, 'backward')
}

function orderEquals(a: readonly string[], b: readonly string[]): boolean {
  if (a.length !== b.length) return false
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false
  return true
}
