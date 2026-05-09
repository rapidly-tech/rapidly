/**
 * Zoom-to-fit / zoom-to-selection helpers.
 *
 * Both share one engine: compute the union bounding box of a chosen
 * element set, then call ``viewportToFitBounds`` to centre + scale.
 *
 * Returns the new viewport so the caller can hand it to the renderer
 * (we don't write back here — the renderer is the canonical owner of
 * viewport state). Returns ``null`` when there's nothing to fit, so
 * the caller can decide whether to fall back to "reset" or do nothing.
 */

import type { CollabElement } from './elements'
import type { Viewport } from './viewport'
import { viewportToFitBounds } from './viewport'

interface BBox {
  x: number
  y: number
  width: number
  height: number
}

/** Union bounding box for a set of elements. ``null`` for empty
 *  inputs so callers can short-circuit without a sentinel value. */
export function unionBoundsForElements(
  elements: readonly CollabElement[],
): BBox | null {
  if (elements.length === 0) return null
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const el of elements) {
    if (el.x < minX) minX = el.x
    if (el.y < minY) minY = el.y
    if (el.x + el.width > maxX) maxX = el.x + el.width
    if (el.y + el.height > maxY) maxY = el.y + el.height
  }
  return { x: minX, y: minY, width: maxX - minX, height: maxY - minY }
}

export interface ZoomToFitOptions {
  /** CSS pixels of padding on every side. Default 24. */
  padding?: number
  /** Scale to use when the bounds are degenerate (e.g. a single
   *  zero-width element or empty input). Default 1 (100%). */
  fallbackScale?: number
}

/** Compute a viewport that fits ALL elements. Returns null when the
 *  list is empty so the caller can decide whether to leave the
 *  viewport untouched or fall back to a "reset" view. */
export function zoomToFit(
  elements: readonly CollabElement[],
  canvasWidth: number,
  canvasHeight: number,
  options: ZoomToFitOptions = {},
): Viewport | null {
  const bounds = unionBoundsForElements(elements)
  if (!bounds) return null
  return viewportToFitBounds(bounds, canvasWidth, canvasHeight, {
    padding: options.padding,
    scale: options.fallbackScale,
  })
}

/** Compute a viewport that fits ONLY the selected elements. Returns
 *  null when no selected element is present in the store (or the
 *  selection is empty). */
export function zoomToSelection(
  elements: readonly CollabElement[],
  selected: ReadonlySet<string>,
  canvasWidth: number,
  canvasHeight: number,
  options: ZoomToFitOptions = {},
): Viewport | null {
  if (selected.size === 0) return null
  const subset: CollabElement[] = []
  for (const el of elements) {
    if (selected.has(el.id)) subset.push(el)
  }
  return zoomToFit(subset, canvasWidth, canvasHeight, options)
}
