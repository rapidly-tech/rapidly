/**
 * Rotation handle math for the Collab v2 whiteboard.
 *
 * The rotation handle sits a fixed screen-pixel offset above the
 * top-mid resize handle, in the rotated frame of the element. Dragging
 * it spins the element around its centre. Holding Shift snaps the
 * angle to 15° increments — fine enough for typical layout work
 * without requiring pixel-perfect pointer control.
 *
 * Pure module — no DOM, no store writes. The select tool owns the
 * gesture and the selection overlay paints the handle.
 */

import { rotatePoint } from './resize'
import type { Viewport } from './viewport'

/** Screen-pixel distance from the top edge of the element to the
 *  rotation handle's centre. Picked to clear the resize handle below
 *  it (which the desktop preset draws at 8 px) plus a comfortable
 *  finger-friendly gap. */
export const ROTATION_HANDLE_OFFSET_PX = 24

/** World-space position of the rotation handle, including the
 *  element's current rotation. The select tool feeds this to the
 *  hit-test and the overlay paints it at exactly this point. */
export function rotationHandlePosition(
  el: { x: number; y: number; width: number; height: number; angle: number },
  vp: Viewport,
): { x: number; y: number } {
  // Handle lives ``offset / scale`` world-units above the top edge,
  // pre-rotation; we then rotate around the element centre to land in
  // world space.
  const offsetWorld = ROTATION_HANDLE_OFFSET_PX / Math.max(vp.scale, 0.01)
  const cx = el.x + el.width / 2
  const cy = el.y + el.height / 2
  const handleX = cx
  const handleY = el.y - offsetWorld
  return rotatePoint(handleX, handleY, cx, cy, el.angle)
}

/** Hit-test a screen-space point against the rotation handle. Returns
 *  ``true`` when the point is within ``radiusScreenPx`` of the
 *  handle's screen position. */
export function hitRotationHandle(
  el: { x: number; y: number; width: number; height: number; angle: number },
  vp: Viewport,
  screenX: number,
  screenY: number,
  radiusScreenPx: number = 10,
): boolean {
  const w = rotationHandlePosition(el, vp)
  const sx = (w.x - vp.scrollX) * vp.scale
  const sy = (w.y - vp.scrollY) * vp.scale
  return Math.hypot(sx - screenX, sy - screenY) <= radiusScreenPx
}

/** Angle from a centre point to a query point, in radians, measured
 *  from the +x axis. The ``y`` axis grows downward in canvas space, so
 *  positive angles correspond to clockwise rotation — which matches
 *  what ``el.angle`` already encodes everywhere else. */
export function angleFromCentre(
  cx: number,
  cy: number,
  pointX: number,
  pointY: number,
): number {
  return Math.atan2(pointY - cy, pointX - cx)
}

/** Snap an angle to the nearest 15° increment when ``shift`` is set;
 *  otherwise return as-is. Implementation snaps in radians directly
 *  so we never round-trip through degrees and accumulate float drift. */
export const ROTATION_SNAP_RAD = (15 * Math.PI) / 180

export function snapAngleToIncrement(
  angle: number,
  shift: boolean,
  step: number = ROTATION_SNAP_RAD,
): number {
  if (!shift) return angle
  return Math.round(angle / step) * step
}

/** Compute the element's new angle for a rotation gesture. ``initial``
 *  is the angle from centre to the pointer at gesture start; ``current``
 *  is the same at the current pointer position. The element rotates by
 *  the delta, layered on top of its starting angle. ``shift`` snaps to
 *  the 15° increment. */
export function nextAngle(
  initialPointerAngle: number,
  currentPointerAngle: number,
  initialElementAngle: number,
  shift: boolean,
): number {
  const delta = currentPointerAngle - initialPointerAngle
  const raw = initialElementAngle + delta
  return snapAngleToIncrement(raw, shift)
}
