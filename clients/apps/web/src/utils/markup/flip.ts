/**
 * Flip operations for the Collab v2 whiteboard.
 *
 * ``flipHorizontal`` and ``flipVertical`` mirror the selected
 * elements across the centre line of their collective bounding box:
 *
 *   - Single element: mirror across its own centre — the element
 *     stays in place.
 *   - Multiple elements: mirror across the bounding box's mid-x
 *     (horizontal) or mid-y (vertical) — relative positions flip
 *     too, so a "before/after" diagram becomes "after/before".
 *
 * Per-element handling:
 *   - Rect / ellipse / diamond / sticky / image / frame / embed /
 *     text — translate position so the centre lands at
 *     ``(2*pivot - oldCentre)``; rotation negates around the flip
 *     axis (h: ``angle = -angle``; v: ``angle = π - angle``).
 *   - Line / arrow / freedraw — points are mirrored in element-local
 *     space (we negate ``px`` for h or ``py`` for v) and the same
 *     position-mirror is applied at the element level.
 *
 * Locked elements are skipped.
 *
 * Writes happen in a single store transaction so undo treats the
 * whole flip as one step.
 */

import type { ElementStore } from './element-store'
import type {
  ArrowElement,
  CollabElement,
  FreeDrawElement,
  LineElement,
} from './elements'

export type FlipAxis = 'horizontal' | 'vertical'

type LinearLike = LineElement | ArrowElement

interface BBox {
  minX: number
  minY: number
  maxX: number
  maxY: number
}

function isLinear(el: CollabElement): el is LinearLike {
  return el.type === 'line' || el.type === 'arrow'
}

function isFreeDraw(el: CollabElement): el is FreeDrawElement {
  return el.type === 'freedraw'
}

function elementBBox(el: CollabElement): BBox {
  return {
    minX: el.x,
    minY: el.y,
    maxX: el.x + el.width,
    maxY: el.y + el.height,
  }
}

function unionBBox(els: readonly CollabElement[]): BBox | null {
  if (els.length === 0) return null
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const el of els) {
    const b = elementBBox(el)
    if (b.minX < minX) minX = b.minX
    if (b.minY < minY) minY = b.minY
    if (b.maxX > maxX) maxX = b.maxX
    if (b.maxY > maxY) maxY = b.maxY
  }
  return { minX, minY, maxX, maxY }
}

function buildPatch(
  el: CollabElement,
  axis: FlipAxis,
  pivot: number,
): Record<string, unknown> {
  const oldCentreX = el.x + el.width / 2
  const oldCentreY = el.y + el.height / 2
  const patch: Record<string, unknown> = {}

  if (axis === 'horizontal') {
    const newCentreX = 2 * pivot - oldCentreX
    patch.x = newCentreX - el.width / 2
    patch.angle = -el.angle
  } else {
    const newCentreY = 2 * pivot - oldCentreY
    patch.y = newCentreY - el.height / 2
    patch.angle = Math.PI - el.angle
  }

  // Mirror per-point coordinates for path-style elements so the shape
  // visually flips, not just the bounding box. ``points`` is a flat
  // array — pairs ``[x0,y0,x1,y1,...]`` for line/arrow, triples
  // ``[x0,y0,p0,x1,y1,p1,...]`` for freedraw.
  if (isLinear(el)) {
    const out = el.points.slice()
    for (let i = 0; i < out.length; i += 2) {
      if (axis === 'horizontal') out[i] = el.width - out[i]
      else out[i + 1] = el.height - out[i + 1]
    }
    patch.points = out
  } else if (isFreeDraw(el)) {
    const out = el.points.slice()
    for (let i = 0; i < out.length; i += 3) {
      if (axis === 'horizontal') out[i] = el.width - out[i]
      else out[i + 1] = el.height - out[i + 1]
    }
    patch.points = out
  }

  return patch
}

/** Flip the selected elements across the requested axis.
 *  Returns the count of elements actually mutated (locked elements
 *  and unknown ids don't count). */
export function flip(
  store: ElementStore,
  selected: ReadonlySet<string>,
  axis: FlipAxis,
): number {
  if (selected.size === 0) return 0
  const els: CollabElement[] = []
  for (const el of store.list()) {
    if (selected.has(el.id) && !el.locked) els.push(el)
  }
  if (els.length === 0) return 0

  const bbox = unionBBox(els)!
  const pivot =
    axis === 'horizontal'
      ? (bbox.minX + bbox.maxX) / 2
      : (bbox.minY + bbox.maxY) / 2

  store.transact(() => {
    for (const el of els) {
      store.update(el.id, buildPatch(el, axis, pivot))
    }
  })

  return els.length
}

export function flipHorizontal(
  store: ElementStore,
  selected: ReadonlySet<string>,
): number {
  return flip(store, selected, 'horizontal')
}

export function flipVertical(
  store: ElementStore,
  selected: ReadonlySet<string>,
): number {
  return flip(store, selected, 'vertical')
}
