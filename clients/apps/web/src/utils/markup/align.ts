/**
 * Align + distribute operations for multi-element selections.
 *
 * Six align ops:
 *   left / centreX / right    — snap each element's bounding-box edge
 *                                or centre to the union bbox edge.
 *   top  / centreY / bottom   — vertical equivalents.
 *
 * Two distribute ops:
 *   horizontal / vertical      — space the elements so the gaps
 *                                between consecutive bounding boxes
 *                                are equal. Requires ≥3 elements.
 *
 * Locked elements are skipped. Single-element selections are no-ops.
 * The whole batch is a single Yjs transaction → single undo step,
 * atomic remote frame.
 */

import type { ElementStore } from './element-store'
import type { CollabElement } from './elements'

export type AlignAxis =
  | 'left'
  | 'centreX'
  | 'right'
  | 'top'
  | 'centreY'
  | 'bottom'

export type DistributeAxis = 'horizontal' | 'vertical'

interface BBox {
  minX: number
  minY: number
  maxX: number
  maxY: number
}

function bboxOf(el: CollabElement): BBox {
  return {
    minX: el.x,
    minY: el.y,
    maxX: el.x + el.width,
    maxY: el.y + el.height,
  }
}

function unionBBox(els: readonly CollabElement[]): BBox {
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const el of els) {
    const b = bboxOf(el)
    if (b.minX < minX) minX = b.minX
    if (b.minY < minY) minY = b.minY
    if (b.maxX > maxX) maxX = b.maxX
    if (b.maxY > maxY) maxY = b.maxY
  }
  return { minX, minY, maxX, maxY }
}

function selectedUnlocked(
  store: ElementStore,
  selected: ReadonlySet<string>,
): CollabElement[] {
  const out: CollabElement[] = []
  for (const el of store.list()) {
    if (selected.has(el.id) && !el.locked) out.push(el)
  }
  return out
}

/** Align the selection along the given axis.
 *  Returns the count of elements actually mutated. */
export function align(
  store: ElementStore,
  selected: ReadonlySet<string>,
  axis: AlignAxis,
): number {
  const els = selectedUnlocked(store, selected)
  if (els.length < 2) return 0
  const bbox = unionBBox(els)

  store.transact(() => {
    for (const el of els) {
      const b = bboxOf(el)
      const patch: Record<string, number> = {}
      switch (axis) {
        case 'left':
          patch.x = bbox.minX
          break
        case 'right':
          patch.x = bbox.maxX - el.width
          break
        case 'centreX':
          patch.x = (bbox.minX + bbox.maxX) / 2 - el.width / 2
          break
        case 'top':
          patch.y = bbox.minY
          break
        case 'bottom':
          patch.y = bbox.maxY - el.height
          break
        case 'centreY':
          patch.y = (bbox.minY + bbox.maxY) / 2 - el.height / 2
          break
      }
      // Only emit the update if the value actually changes (avoids
      // bumping ``version`` for already-aligned elements).
      const current =
        axis === 'top' || axis === 'bottom' || axis === 'centreY'
          ? b.minY
          : b.minX
      const next =
        axis === 'top' || axis === 'bottom' || axis === 'centreY'
          ? patch.y
          : patch.x
      if (current !== next) {
        store.update(el.id, patch)
      }
    }
  })

  return els.length
}

/** Distribute the selection so the GAP between consecutive bounding
 *  boxes is equal. Anchor elements (the leftmost/topmost and the
 *  rightmost/bottommost) stay in place; every interior element is
 *  positioned so that ``b[i].minX = b[i-1].maxX + gap`` (or vertical
 *  equivalent).
 *
 *  Returns the count of moved elements (or 0 when the selection has
 *  fewer than 3 unlocked elements). */
export function distribute(
  store: ElementStore,
  selected: ReadonlySet<string>,
  axis: DistributeAxis,
): number {
  const els = selectedUnlocked(store, selected)
  if (els.length < 3) return 0

  // Sort by leading edge along the axis. Stable sort preserves
  // selection order for ties so the result is deterministic.
  const sorted = [...els].sort((a, b) => {
    if (axis === 'horizontal') return a.x - b.x
    return a.y - b.y
  })

  let totalSize = 0
  for (const el of sorted) {
    totalSize += axis === 'horizontal' ? el.width : el.height
  }
  const first = sorted[0]
  const last = sorted[sorted.length - 1]
  const span =
    axis === 'horizontal'
      ? last.x + last.width - first.x
      : last.y + last.height - first.y
  // Gap between consecutive bounding boxes. (n-1) gaps for n elements.
  const gap = (span - totalSize) / (sorted.length - 1)

  let moved = 0
  store.transact(() => {
    let cursor =
      axis === 'horizontal' ? first.x + first.width : first.y + first.height
    for (let i = 1; i < sorted.length - 1; i++) {
      const el = sorted[i]
      const target = cursor + gap
      const patch: Record<string, number> = {}
      if (axis === 'horizontal') {
        if (el.x !== target) {
          patch.x = target
          store.update(el.id, patch)
          moved++
        }
        cursor = target + el.width
      } else {
        if (el.y !== target) {
          patch.y = target
          store.update(el.id, patch)
          moved++
        }
        cursor = target + el.height
      }
    }
  })

  return moved
}
