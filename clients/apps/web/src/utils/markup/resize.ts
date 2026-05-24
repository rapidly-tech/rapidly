/**
 * Resize-handle math for the Collab v2 whiteboard.
 *
 * Pure functions — no DOM, no store writes. The select tool owns the
 * pointer gesture and calls into here for handle positions, hit-
 * testing, and applying a drag to an element.
 *
 * Handles live in element-local coordinates (origin at the element's
 * top-left, pre-rotation). Screen hit-testing unprojects the pointer
 * through the element's rotation before comparing.
 */

import type { CollabElement } from './elements'
import type { Viewport } from './viewport'

export type HandleId = 'nw' | 'n' | 'ne' | 'e' | 'se' | 's' | 'sw' | 'w'

/** World-space corner / edge-midpoint positions of every resize
 *  handle, **pre-rotation** (the element's own coordinate frame). */
export function handleWorldPositions(
  el: CollabElement,
): Record<HandleId, { x: number; y: number }> {
  const { x, y, width, height } = el
  const cx = x + width / 2
  const cy = y + height / 2
  return {
    nw: { x, y },
    n: { x: cx, y },
    ne: { x: x + width, y },
    e: { x: x + width, y: cy },
    se: { x: x + width, y: y + height },
    s: { x: cx, y: y + height },
    sw: { x, y: y + height },
    w: { x, y: cy },
  }
}

/** Apply the element's rotation around its centre to a world point.
 *  Used to transform a handle's pre-rotation position into the
 *  rotated world position for rendering + hit-testing. */
export function rotatePoint(
  px: number,
  py: number,
  cx: number,
  cy: number,
  angle: number,
): { x: number; y: number } {
  if (angle === 0) return { x: px, y: py }
  const cos = Math.cos(angle)
  const sin = Math.sin(angle)
  const dx = px - cx
  const dy = py - cy
  return { x: cx + dx * cos - dy * sin, y: cy + dx * sin + dy * cos }
}

/** Rotated world positions for every handle — cheaper to pre-compute
 *  once per frame than per handle per hit-test. */
export function handleRotatedPositions(
  el: CollabElement,
): Record<HandleId, { x: number; y: number }> {
  const raw = handleWorldPositions(el)
  const cx = el.x + el.width / 2
  const cy = el.y + el.height / 2
  const out = {} as Record<HandleId, { x: number; y: number }>
  for (const k of Object.keys(raw) as HandleId[]) {
    out[k] = rotatePoint(raw[k].x, raw[k].y, cx, cy, el.angle)
  }
  return out
}

/** Hit-test a screen-space point against every handle on ``el``.
 *  Handle sizes stay constant in screen pixels regardless of zoom,
 *  so we convert the world-space handle positions to screen first.
 *
 *  Returns the handle id whose centre is within ``radiusScreenPx`` of
 *  the query point, or ``null``. */
export function hitHandle(
  el: CollabElement,
  vp: Viewport,
  screenX: number,
  screenY: number,
  radiusScreenPx = 10,
): HandleId | null {
  const worldHandles = handleRotatedPositions(el)
  let best: { id: HandleId; dist: number } | null = null
  for (const id of Object.keys(worldHandles) as HandleId[]) {
    const w = worldHandles[id]
    const sx = (w.x - vp.scrollX) * vp.scale
    const sy = (w.y - vp.scrollY) * vp.scale
    const dx = sx - screenX
    const dy = sy - screenY
    const dist = Math.hypot(dx, dy)
    if (dist <= radiusScreenPx && (!best || dist < best.dist)) {
      best = { id, dist }
    }
  }
  return best?.id ?? null
}

/** Per-handle cursor to surface during hover / while dragging. Kept
 *  simple — the 8 directional resize cursors are all CSS standard. */
export function cursorForHandle(h: HandleId): string {
  switch (h) {
    case 'n':
    case 's':
      return 'ns-resize'
    case 'e':
    case 'w':
      return 'ew-resize'
    case 'nw':
    case 'se':
      return 'nwse-resize'
    case 'ne':
    case 'sw':
      return 'nesw-resize'
  }
}

/** Snapshot of the element's bounding box at the start of a resize
 *  gesture. Used so per-pointermove updates derive from the anchor
 *  rather than accumulating floating-point drift from the previous
 *  frame's partial result. */
export interface ResizeAnchor {
  x: number
  y: number
  width: number
  height: number
  angle: number
}

export function anchorFrom(el: CollabElement): ResizeAnchor {
  return {
    x: el.x,
    y: el.y,
    width: el.width,
    height: el.height,
    angle: el.angle,
  }
}

/** Compute the element's new (x, y, width, height) given a drag on
 *  ``handle`` from ``startWorldX/Y`` to ``curWorldX/Y``. Ignores
 *  rotation for now — for a rotated element, the caller should
 *  un-rotate the drag delta around the anchor's centre first. The
 *  select tool does that before calling in.
 *
 *  When ``aspectLock`` is set (Shift held), corner handles preserve
 *  the anchor's width/height ratio: the dominant axis (longer
 *  effective drag) wins and the other axis derives from the locked
 *  ratio. Edge handles ignore the flag — there's no second axis to
 *  constrain.
 *
 *  Minimum width / height is 1 so a handle can't collapse the element
 *  to a degenerate rect that hit-testing rejects.
 */
export function applyResize(
  anchor: ResizeAnchor,
  handle: HandleId,
  dx: number,
  dy: number,
  aspectLock: boolean = false,
): { x: number; y: number; width: number; height: number } {
  if (aspectLock && isCornerHandle(handle)) {
    const locked = lockAspectDelta(anchor, handle, dx, dy)
    dx = locked.dx
    dy = locked.dy
  }
  let { x, y, width, height } = anchor
  const right = x + width
  const bottom = y + height

  switch (handle) {
    case 'nw':
      x = anchor.x + dx
      y = anchor.y + dy
      width = right - x
      height = bottom - y
      break
    case 'n':
      y = anchor.y + dy
      height = bottom - y
      break
    case 'ne':
      y = anchor.y + dy
      width = anchor.width + dx
      height = bottom - y
      break
    case 'e':
      width = anchor.width + dx
      break
    case 'se':
      width = anchor.width + dx
      height = anchor.height + dy
      break
    case 's':
      height = anchor.height + dy
      break
    case 'sw':
      x = anchor.x + dx
      width = right - x
      height = anchor.height + dy
      break
    case 'w':
      x = anchor.x + dx
      width = right - x
      break
  }

  // Flipping — dragging past the opposite edge should continue to
  // work rather than clamp to 0. Normalise so width / height remain
  // positive and the origin tracks the smaller corner.
  if (width < 0) {
    x += width
    width = -width
  }
  if (height < 0) {
    y += height
    height = -height
  }

  // Degenerate clamps — 1 world unit keeps the element hit-testable.
  width = Math.max(1, width)
  height = Math.max(1, height)

  return { x, y, width, height }
}

/** Whether ``handle`` controls two axes simultaneously. Edge handles
 *  (n / s / e / w) only move one dimension; corner handles can lock
 *  aspect because they have a meaningful ratio between dx and dy. */
function isCornerHandle(handle: HandleId): boolean {
  return (
    handle === 'nw' || handle === 'ne' || handle === 'sw' || handle === 'se'
  )
}

/** Project ``(dx, dy)`` onto the anchor's diagonal so the resulting
 *  resize preserves the anchor's aspect ratio. The dominant axis (the
 *  one whose drag implies a larger uniform scale) wins; the other
 *  axis is derived from it. Each corner handle has its own sign
 *  conventions — nw drags negative, se positive, etc. */
export function lockAspectDelta(
  anchor: ResizeAnchor,
  handle: HandleId,
  dx: number,
  dy: number,
): { dx: number; dy: number } {
  const aw = anchor.width || 1
  const ah = anchor.height || 1
  // For each corner, ``signX`` and ``signY`` describe whether a
  // positive scale corresponds to a positive dx / dy. nw drags up-left
  // to grow → both negative; se drags down-right to grow → both
  // positive; ne is up-right → dy negative, dx positive; sw is the
  // mirror.
  let signX = 1
  let signY = 1
  if (handle === 'nw') {
    signX = -1
    signY = -1
  } else if (handle === 'ne') {
    signY = -1
  } else if (handle === 'sw') {
    signX = -1
  }
  // Effective uniform scale implied by each axis. Multiply by the
  // sign so a positive scale always means ""bigger"" regardless of
  // which corner is dragged.
  const scaleFromX = (signX * dx) / aw
  const scaleFromY = (signY * dy) / ah
  // Larger absolute scale wins — the user's pointer travels further
  // along that axis so its motion should drive the resize.
  const scale =
    Math.abs(scaleFromX) >= Math.abs(scaleFromY) ? scaleFromX : scaleFromY
  return {
    dx: signX * scale * aw,
    dy: signY * scale * ah,
  }
}
