/**
 * Presentation mode — pan + zoom the viewport to visit each element
 * (or ``frame`` element) in sequence.
 *
 * This module is **pure math**: it produces the viewport that would
 * fit a given world-space bounds onto a canvas of a given size, and
 * it walks an element list into an ordered frame list. The demo page
 * wires a fullscreen + keyboard handler on top.
 *
 * Frame ordering
 * --------------
 * When at least one element has ``type === 'frame'``, frames drive
 * the sequence (ordered by ``zIndex``). Otherwise every element
 * contributes one frame, still ordered by ``zIndex``. This means a
 * user who hasn't groped around with the Frame tool yet still gets a
 * usable presentation walk-through out of any scene.
 */

import type { CollabElement } from './elements'
import { paintOrder } from './elements'
import { clampScale, type Viewport } from './viewport'

/** A single frame in the presentation sequence. The ``bounds`` drive
 *  the camera fit; ``id`` is kept for debugging and for a future
 *  ""current slide"" indicator. */
export interface PresentationFrame {
  id: string
  bounds: { x: number; y: number; width: number; height: number }
}

export interface ComputeFramesOptions {
  /** World-space padding applied to the fit rect. Default 32 world
   *  units — enough for stroke + label halos not to clip. */
  padding?: number
}

const DEFAULT_PADDING = 32

/** Walk the element list into a presentation sequence. Returns an
 *  empty array for an empty scene so the caller can short-circuit. */
export function computeFrames(
  elements: readonly CollabElement[],
  options: ComputeFramesOptions = {},
): PresentationFrame[] {
  if (elements.length === 0) return []
  const padding = options.padding ?? DEFAULT_PADDING

  // Frame-type elements take precedence when any exist.
  const framesOnly = elements.filter((el) => el.type === 'frame')
  const source = framesOnly.length > 0 ? framesOnly : elements.slice()
  const ordered = source.slice().sort(paintOrder)

  return ordered.map((el) => ({
    id: el.id,
    bounds: {
      x: el.x - padding,
      y: el.y - padding,
      width: el.width + padding * 2,
      height: el.height + padding * 2,
    },
  }))
}

/** Compute the viewport that fits ``bounds`` (world coords) into a
 *  canvas of ``canvasWidth × canvasHeight`` (screen pixels). The
 *  result is clamped to the viewport's legal scale range. */
export function viewportForBounds(
  bounds: { x: number; y: number; width: number; height: number },
  canvasWidth: number,
  canvasHeight: number,
): Viewport {
  if (bounds.width <= 0 || bounds.height <= 0) {
    return { scale: 1, scrollX: bounds.x, scrollY: bounds.y }
  }
  if (canvasWidth <= 0 || canvasHeight <= 0) {
    return { scale: 1, scrollX: bounds.x, scrollY: bounds.y }
  }
  const sx = canvasWidth / bounds.width
  const sy = canvasHeight / bounds.height
  const scale = clampScale(Math.min(sx, sy))
  // Centre the bounds inside the canvas.
  const fitWorldWidth = canvasWidth / scale
  const fitWorldHeight = canvasHeight / scale
  const scrollX = bounds.x - (fitWorldWidth - bounds.width) / 2
  const scrollY = bounds.y - (fitWorldHeight - bounds.height) / 2
  return { scale, scrollX, scrollY }
}

/** Advance or rewind the current frame index, clamped to the list.
 *  Exported so the demo + ``useCollabRoom`` hook share one policy
 *  (no wrap-around — the last frame stays the last frame on extra
 *  arrow-key presses; typical presentation behaviour). */
export function advanceFrame(
  current: number,
  total: number,
  direction: 1 | -1,
): number {
  if (total === 0) return 0
  const next = current + direction
  if (next < 0) return 0
  if (next >= total) return total - 1
  return next
}
