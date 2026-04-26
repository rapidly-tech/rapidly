/**
 * Snap-to-objects (alignment guides) for the Collab v2 whiteboard.
 *
 * While the user drags one or more elements, this module looks at the
 * dragged group's bounding box and the bounding boxes of all other
 * (stationary) elements. When a candidate edge or centre line is
 * within a fixed pixel threshold of a stationary element's matching
 * line, we snap the drag delta so the two lines coincide.
 *
 * The tool only consumes a single ``Snap`` per axis — the closest
 * candidate wins. The guide-render overlay (separate module) reads the
 * returned ``guides`` to paint a faint dashed line at every aligned
 * pair so the user sees what they snapped to.
 *
 * Threshold lives in **screen pixels** (not world units) so the
 * affordance feels consistent across zoom levels — at zoom 4 a 6-px
 * gap in screen-space is 1.5 world units; at zoom 0.5 it's 12 world
 * units. The caller passes ``scale`` so we can convert internally.
 *
 * Pure module — no canvas, no Yjs. ``select.ts`` calls into it during
 * the move gesture; tests pin the math without a renderer.
 */

import type { Bounds } from './export'

/** A single alignment match. ``world`` is the world-space coordinate
 *  of the alignment line (an x for vertical guides, a y for
 *  horizontal). The select tool uses it to render guides; the snap
 *  delta itself is computed alongside in ``snapDelta``. */
export interface SnapGuide {
  axis: 'x' | 'y'
  /** World-space coord of the guide line. */
  world: number
  /** World-space extent of the guide along the perpendicular axis,
   *  spanning from the topmost (or leftmost) participant to the
   *  bottommost (or rightmost). Renderers cap the line to this range
   *  rather than running it across the entire canvas. */
  start: number
  end: number
}

export interface SnapResult {
  /** Adjusted drag delta — caller adds it to each anchor in lieu of
   *  the raw pointer delta. Equal to the input delta on no-snap. */
  dx: number
  dy: number
  guides: SnapGuide[]
}

/** Default screen-space snap threshold. ~5 CSS pixels feels close
 *  enough to "deliberate" alignment without grabbing every passing
 *  edge. Excalidraw uses a similar value. */
export const DEFAULT_SNAP_THRESHOLD_PX = 5

/** Compute the dragged group's lines (edges + centre) along one axis. */
function lineSet(
  bbox: Bounds,
  axis: 'x' | 'y',
): { min: number; mid: number; max: number } {
  if (axis === 'x') {
    return {
      min: bbox.x,
      mid: bbox.x + bbox.width / 2,
      max: bbox.x + bbox.width,
    }
  }
  return {
    min: bbox.y,
    mid: bbox.y + bbox.height / 2,
    max: bbox.y + bbox.height,
  }
}

/** Look for the closest snap candidate on a single axis. Returns the
 *  delta to add to the dragged bbox to align with the closest static
 *  line, plus the guide describing the match. */
function bestSnap(
  draggedAfterDelta: Bounds,
  static_: readonly Bounds[],
  axis: 'x' | 'y',
  thresholdWorld: number,
): { delta: number; guide: SnapGuide | null } {
  const dragged = lineSet(draggedAfterDelta, axis)
  let bestDelta = 0
  let bestDistance = thresholdWorld + 1
  let bestGuide: SnapGuide | null = null

  for (const s of static_) {
    const target = lineSet(s, axis)
    // 3 dragged candidates × 3 static candidates = 9 pairings on this
    // axis. We only consider matching slot-to-slot to avoid weirdness
    // (e.g. snapping our left to their centre is rarely what the user
    // wants and is confusing in the UI).
    for (const slot of ['min', 'mid', 'max'] as const) {
      const draggedV = dragged[slot]
      const targetV = target[slot]
      const distance = Math.abs(targetV - draggedV)
      if (distance > thresholdWorld) continue
      if (distance >= bestDistance) continue
      bestDistance = distance
      bestDelta = targetV - draggedV
      // Guide spans across both bboxes on the perpendicular axis.
      const perp = axis === 'x' ? ['y', 'height'] : ['x', 'width']
      const a0 = (draggedAfterDelta as unknown as Record<string, number>)[
        perp[0]
      ]
      const a1 =
        a0 + (draggedAfterDelta as unknown as Record<string, number>)[perp[1]]
      const b0 = (s as unknown as Record<string, number>)[perp[0]]
      const b1 = b0 + (s as unknown as Record<string, number>)[perp[1]]
      bestGuide = {
        axis,
        world: targetV,
        start: Math.min(a0, b0),
        end: Math.max(a1, b1),
      }
    }
  }

  return { delta: bestDelta, guide: bestGuide }
}

export interface SnapInputs {
  /** AABB of the dragged group at the **start** of the gesture (i.e.
   *  before the current drag delta is applied). */
  draggedBbox: Bounds
  /** Raw drag delta in world coordinates, as the caller would apply
   *  it without any snapping. */
  dx: number
  dy: number
  /** Bboxes of every stationary element to test against. The select
   *  tool excludes the dragged ids before passing this in. */
  staticBboxes: readonly Bounds[]
  /** Current viewport scale — converts threshold from screen px to
   *  world units. */
  scale: number
  /** Optional override for the threshold (screen px). Defaults to 5. */
  thresholdPx?: number
}

/** Snap a drag delta to the nearest object alignment along each axis
 *  independently. Returns the (possibly adjusted) delta plus any
 *  guides to render. */
export function snapToObjects(inputs: SnapInputs): SnapResult {
  const { draggedBbox, dx, dy, staticBboxes, scale } = inputs
  if (staticBboxes.length === 0) {
    return { dx, dy, guides: [] }
  }
  const thresholdPx = inputs.thresholdPx ?? DEFAULT_SNAP_THRESHOLD_PX
  const thresholdWorld = thresholdPx / Math.max(scale, 0.01)

  const draggedAfter: Bounds = {
    x: draggedBbox.x + dx,
    y: draggedBbox.y + dy,
    width: draggedBbox.width,
    height: draggedBbox.height,
  }

  const xSnap = bestSnap(draggedAfter, staticBboxes, 'x', thresholdWorld)
  const ySnap = bestSnap(draggedAfter, staticBboxes, 'y', thresholdWorld)

  const guides: SnapGuide[] = []
  if (xSnap.guide) guides.push(xSnap.guide)
  if (ySnap.guide) guides.push(ySnap.guide)

  return {
    dx: dx + xSnap.delta,
    dy: dy + ySnap.delta,
    guides,
  }
}

/** Bbox helper for an element. Only x/y/width/height, ignoring rotation
 *  — the alignment heuristic uses the element's local AABB which is
 *  what the user sees as its "footprint" before rotation. Matching
 *  Excalidraw behaviour: rotated elements snap by their AABB centre. */
export function bboxFromElement(el: {
  x: number
  y: number
  width: number
  height: number
}): Bounds {
  return { x: el.x, y: el.y, width: el.width, height: el.height }
}

/** AABB covering many elements. Used for multi-select drag. Returns
 *  null on empty input — the caller falls back to no-snap. */
export function unionBbox(
  els: readonly { x: number; y: number; width: number; height: number }[],
): Bounds | null {
  if (els.length === 0) return null
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const el of els) {
    if (el.x < minX) minX = el.x
    if (el.y < minY) minY = el.y
    const ex = el.x + el.width
    const ey = el.y + el.height
    if (ex > maxX) maxX = ex
    if (ey > maxY) maxY = ey
  }
  return { x: minX, y: minY, width: maxX - minX, height: maxY - minY }
}
