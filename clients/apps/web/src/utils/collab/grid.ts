/**
 * Grid + snap-to-grid for the Collab v2 whiteboard.
 *
 * Two surfaces:
 *
 *  - ``snapToGrid(value, gridSize)`` — pure rounding helper used by
 *    tools (rect / ellipse / move / resize / draw) when grid-snap is
 *    enabled. Snaps to the NEAREST grid line so the user-visible
 *    motion mirrors the cursor position rather than always rounding
 *    down.
 *  - ``drawGrid(ctx, viewport, canvasW, canvasH, gridSize)`` — paints
 *    the grid as a thin dotted overlay in canvas (screen) coords. The
 *    grid only renders when the on-screen spacing exceeds 6 px so
 *    extreme zoom-out levels don't paint a moiré of overlapping
 *    pixels (and don't murder the GPU). The dot colour mirrors the
 *    document text-faded token in CSS so it works in light + dark
 *    mode without a branch.
 *
 * The default grid size is 20 world units — small enough to feel
 * responsive on close-up work and large enough to be a useful
 * alignment guide at zoom 1.0. Stored alongside the viewport so the
 * Phase-X command palette can let a power user pick a different size.
 */

import type { Viewport } from './viewport'

export const DEFAULT_GRID_SIZE = 20

/** Threshold below which we hide the grid: when the on-screen spacing
 *  between grid lines drops under ``MIN_VISIBLE_SPACING`` CSS pixels
 *  the dots become noise / a moiré. Picked to match the eye's
 *  comfortable resolution at 96-dpi. */
const MIN_VISIBLE_SPACING_PX = 6

/** Snap a value to the nearest grid line. Negative values round
 *  toward the same line as their positive mirror so motion is
 *  symmetric across the origin. ``gridSize <= 0`` is a no-op
 *  (defensive — callers shouldn't pass it but the math is undefined). */
export function snapToGrid(value: number, gridSize: number): number {
  if (gridSize <= 0 || !Number.isFinite(gridSize)) return value
  return Math.round(value / gridSize) * gridSize
}

/** Snap an (x, y) point. Convenience wrapper — keeps callers terse. */
export function snapPoint(
  x: number,
  y: number,
  gridSize: number,
): { x: number; y: number } {
  return { x: snapToGrid(x, gridSize), y: snapToGrid(y, gridSize) }
}

/** Snap a screen-space delta (pixels) so dragging at the current
 *  zoom snaps in world units. The conversion is: deltaWorld =
 *  delta / scale; snap; multiply back. */
export function snapDeltaToGrid(
  deltaScreen: number,
  scale: number,
  gridSize: number,
): number {
  if (gridSize <= 0 || scale <= 0) return deltaScreen
  const deltaWorld = deltaScreen / scale
  const snapped = Math.round(deltaWorld / gridSize) * gridSize
  return snapped * scale
}

/** Whether the grid should paint at the given viewport scale. */
export function gridVisibleAt(scale: number, gridSize: number): boolean {
  return scale * gridSize >= MIN_VISIBLE_SPACING_PX
}

/** Paint a dotted grid overlay onto a 2D canvas context. The context
 *  is expected to be in canvas (screen) coords — the renderer resets
 *  the transform with ``ctx.setTransform(1,0,0,1,0,0)`` between the
 *  world-space pass and the overlay pass.
 *
 *  No-op when the on-screen spacing is below the visibility threshold
 *  so we never paint at extreme zoom-out.
 *
 *  Dot colour is read from the supplied ``style`` so callers can plug
 *  in a CSS custom-property or a tailwind token without this module
 *  knowing about either. */
export function drawGrid(
  ctx: CanvasRenderingContext2D,
  vp: Viewport,
  canvasWidth: number,
  canvasHeight: number,
  gridSize: number = DEFAULT_GRID_SIZE,
  style: { dotColor: string; dotRadius?: number } = {
    dotColor: 'rgba(100,116,139,0.35)',
  },
): void {
  if (!gridVisibleAt(vp.scale, gridSize)) return

  const screenSpacing = vp.scale * gridSize
  // World point at canvas (0, 0):
  const worldOriginX = vp.scrollX
  const worldOriginY = vp.scrollY
  // First grid line >= viewport top-left (world coords).
  const firstWorldX = Math.ceil(worldOriginX / gridSize) * gridSize
  const firstWorldY = Math.ceil(worldOriginY / gridSize) * gridSize
  // Convert to screen coords; subsequent lines are evenly spaced by
  // ``screenSpacing`` so we can iterate by += in screen space.
  const firstScreenX = (firstWorldX - worldOriginX) * vp.scale
  const firstScreenY = (firstWorldY - worldOriginY) * vp.scale

  ctx.save()
  ctx.fillStyle = style.dotColor
  const r = style.dotRadius ?? 1
  // Draw one dot per intersection. Cheap on the GPU because the dots
  // are tiny squares (we use fillRect, not arc); good enough at
  // typical desktop sizes (e.g. 1920×1080 / 20-unit grid → ~5,000
  // dots, well within an idle frame budget).
  for (let sy = firstScreenY; sy < canvasHeight; sy += screenSpacing) {
    for (let sx = firstScreenX; sx < canvasWidth; sx += screenSpacing) {
      ctx.fillRect(sx - r / 2, sy - r / 2, r, r)
    }
  }
  ctx.restore()
}
