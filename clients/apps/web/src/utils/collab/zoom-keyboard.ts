/**
 * Keyboard zoom helpers for the Collab v2 whiteboard.
 *
 * Three bindings: Cmd+= to zoom in, Cmd+- to zoom out, Cmd+0 to reset.
 * Each operates on the viewport centre — keyboard zoom doesn't have a
 * pointer position, so we anchor on the canvas mid-point. The wheel
 * zoom (which does have a pointer) keeps using its own at-cursor
 * anchor; both call into ``zoomAt`` so the math stays single-sourced.
 *
 * Pure module — no React, no DOM. The whiteboard's keydown handler
 * resolves the pressed key + canvas size and passes them in.
 */

import { clampScale, zoomAt, type Viewport } from './viewport'

/** Multiplicative step per Cmd+= / Cmd+- press. 1.25 matches Figma /
 *  Excalidraw — small enough to feel precise, large enough that two
 *  presses make a visible difference. */
export const ZOOM_KEYBOARD_STEP = 1.25

/** Default scale Cmd+0 resets to. Excalidraw resets to 1.0; Figma
 *  resets to ""fit page"". We pick 1.0 — the user can ``view.zoomToFit``
 *  from the palette for the alternative. */
export const ZOOM_RESET_SCALE = 1

export type ZoomDirection = 'in' | 'out' | 'reset'

/** Compute the new viewport for one keyboard zoom press. The
 *  ``canvasWidthPx`` / ``canvasHeightPx`` are the on-screen dimensions
 *  of the canvas in CSS pixels — the resulting zoom anchors on the
 *  midpoint so the user's eye doesn't jump. */
export function viewportForKeyboardZoom(
  vp: Viewport,
  direction: ZoomDirection,
  canvasWidthPx: number,
  canvasHeightPx: number,
): Viewport {
  const cx = canvasWidthPx / 2
  const cy = canvasHeightPx / 2
  if (direction === 'reset') {
    return zoomAt(vp, cx, cy, ZOOM_RESET_SCALE)
  }
  const factor =
    direction === 'in' ? ZOOM_KEYBOARD_STEP : 1 / ZOOM_KEYBOARD_STEP
  return zoomAt(vp, cx, cy, clampScale(vp.scale * factor))
}

/** Resolve a KeyboardEvent-like object to a zoom direction, or
 *  ``null`` if the key isn't a zoom binding. The caller pre-checks for
 *  ``metaKey || ctrlKey`` so plain ``=`` / ``-`` / ``0`` don't trigger
 *  zoom — they're tool letters and digit input. */
export function zoomDirectionForKey(key: string): ZoomDirection | null {
  // ``=`` and ``+`` both zoom in: shift on most layouts produces ``+``,
  // unshifted produces ``=``. Either is acceptable.
  if (key === '=' || key === '+') return 'in'
  if (key === '-' || key === '_') return 'out'
  if (key === '0') return 'reset'
  return null
}
