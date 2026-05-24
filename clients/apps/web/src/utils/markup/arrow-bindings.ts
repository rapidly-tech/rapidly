/**
 * Arrow endpoint binding math.
 *
 * An arrow endpoint can "bind" to another shape: when the user drags
 * an endpoint near a rect/ellipse/diamond, we record
 * ``{elementId, focus, gap}`` so moving the target shape updates the
 * arrow endpoint in lock-step (Phase 6b). This file owns the
 * **discovery** side — given a pointer in world coords, is there a
 * shape whose perimeter is close enough to warrant a binding, and if
 * so what are the binding parameters?
 *
 * - ``focus`` ∈ [0, 1] is a parametric position along the target's
 *   perimeter. We store it rather than a concrete point so a later
 *   resize of the target keeps the endpoint at "the same place"
 *   (e.g. centre-right edge).
 * - ``gap`` is the perpendicular distance between the stored perimeter
 *   point and the arrow's actual endpoint. Keeps a visual cushion so
 *   the arrowhead doesn't plough into the shape's outline.
 */

import { isDiamond, isEllipse, isRect, type CollabElement } from './elements'

export interface ArrowBinding {
  elementId: string
  focus: number
  gap: number
}

/** How close (in screen pixels) a pointer must be to a shape to
 *  trigger a binding. Matches ~12 screen px at zoom 1, which we
 *  scale by the viewport for hit tests. */
export const BIND_RADIUS_PX = 12

/** Shape types that support being the target of an arrow binding.
 *  Lines and arrows are excluded because "arrow into arrow" is
 *  awkward UX; freedraw because its perimeter is ill-defined. Frame
 *  and sticky can opt in later. */
function isBindable(el: CollabElement): boolean {
  return isRect(el) || isEllipse(el) || isDiamond(el)
}

/** Project a world-space point onto the closest point of the given
 *  rect / ellipse / diamond perimeter, returning:
 *    - ``focus`` — parametric position (0..1) along the perimeter
 *    - ``dist``  — world-space distance from the projected point
 *    - ``gap``   — signed distance between the actual point and the
 *                  projected one (always positive; the arrow sits
 *                  outside the shape).
 *
 *  For this phase we keep the math simple: project onto the AABB.
 *  Ellipse/diamond get a pass-through of the rect projection, which
 *  is close enough at typical zoom levels. Tightening can land in a
 *  follow-up. */
function project(
  el: CollabElement,
  worldX: number,
  worldY: number,
): { focus: number; dist: number; gap: number } {
  const left = el.x
  const top = el.y
  const right = el.x + el.width
  const bottom = el.y + el.height

  // Snap to nearest edge mid-point or corner via the perimeter
  // parameter. We use an 8-step perimeter: nw, n, ne, e, se, s, sw, w.
  // ``focus`` bins to the closest.
  const candidates: Array<{ x: number; y: number; focus: number }> = [
    { x: left, y: top, focus: 0 / 8 },
    { x: (left + right) / 2, y: top, focus: 1 / 8 },
    { x: right, y: top, focus: 2 / 8 },
    { x: right, y: (top + bottom) / 2, focus: 3 / 8 },
    { x: right, y: bottom, focus: 4 / 8 },
    { x: (left + right) / 2, y: bottom, focus: 5 / 8 },
    { x: left, y: bottom, focus: 6 / 8 },
    { x: left, y: (top + bottom) / 2, focus: 7 / 8 },
  ]

  let best = candidates[0]
  let bestDist = Infinity
  for (const c of candidates) {
    const d = Math.hypot(c.x - worldX, c.y - worldY)
    if (d < bestDist) {
      bestDist = d
      best = c
    }
  }
  return { focus: best.focus, dist: bestDist, gap: bestDist }
}

/** Find a binding target for the given world-space point. Iterates
 *  every bindable element in the store and returns the best (closest)
 *  within ``BIND_RADIUS_PX / viewportScale``. Returns ``null`` when
 *  no shape is close enough. */
export function findBinding(
  elements: readonly CollabElement[],
  worldX: number,
  worldY: number,
  viewportScale: number,
  excludeId?: string,
): ArrowBinding | null {
  const worldRadius = BIND_RADIUS_PX / Math.max(viewportScale, 0.0001)
  let best: { binding: ArrowBinding; dist: number } | null = null
  for (const el of elements) {
    if (!isBindable(el)) continue
    if (excludeId && el.id === excludeId) continue
    const { focus, dist, gap } = project(el, worldX, worldY)
    if (dist <= worldRadius && (!best || dist < best.dist)) {
      best = {
        binding: { elementId: el.id, focus, gap },
        dist,
      }
    }
  }
  return best?.binding ?? null
}

/** Given an updated map of element states, find every arrow whose
 *  start or end binding references one of the supplied ids and
 *  return the patches needed to keep the arrow anchored.
 *
 *  Called by the select tool inside a move/resize transaction so the
 *  bound arrows update in the same atomic frame — remote peers never
 *  observe a half-moved state. */
export function collectBoundArrowPatches(
  elements: readonly CollabElement[],
  changedIds: ReadonlySet<string>,
): Array<{
  id: string
  patch: {
    x: number
    y: number
    width: number
    height: number
    points: number[]
  }
}> {
  if (changedIds.size === 0) return []
  const byId = new Map<string, CollabElement>()
  for (const el of elements) byId.set(el.id, el)
  const out: Array<{
    id: string
    patch: {
      x: number
      y: number
      width: number
      height: number
      points: number[]
    }
  }> = []

  for (const el of elements) {
    if (el.type !== 'arrow') continue
    const startBinding = el.startBinding
    const endBinding = el.endBinding
    const startAffected = !!(
      startBinding && changedIds.has(startBinding.elementId)
    )
    const endAffected = !!(endBinding && changedIds.has(endBinding.elementId))
    if (!startAffected && !endAffected) continue

    // Compute the new absolute start + end points. When a binding
    // exists, resolve against the *current* state of the target. If
    // the binding doesn't exist on that end, translate the existing
    // element-local points back to world space.
    const p = el.points
    if (p.length < 4) continue
    const curStartWorldX = el.x + p[0]
    const curStartWorldY = el.y + p[1]
    const curEndWorldX = el.x + p[p.length - 2]
    const curEndWorldY = el.y + p[p.length - 1]

    let startX = curStartWorldX
    let startY = curStartWorldY
    let endX = curEndWorldX
    let endY = curEndWorldY

    if (startBinding) {
      const target = byId.get(startBinding.elementId)
      if (target) {
        const s = resolveBinding(target, startBinding)
        startX = s.x
        startY = s.y
      }
    }
    if (endBinding) {
      const target = byId.get(endBinding.elementId)
      if (target) {
        const e = resolveBinding(target, endBinding)
        endX = e.x
        endY = e.y
      }
    }

    const minX = Math.min(startX, endX)
    const minY = Math.min(startY, endY)
    const maxX = Math.max(startX, endX)
    const maxY = Math.max(startY, endY)
    out.push({
      id: el.id,
      patch: {
        x: minX,
        y: minY,
        width: maxX - minX,
        height: maxY - minY,
        points: [startX - minX, startY - minY, endX - minX, endY - minY],
      },
    })
  }

  return out
}

/** Resolve a binding to a concrete world-space point. Used when a
 *  bound shape moves / resizes and we need to recompute the arrow
 *  endpoint. */
export function resolveBinding(
  el: CollabElement,
  binding: ArrowBinding,
): { x: number; y: number } {
  // Inverse of ``project``: map the 8-point focus back to the
  // element's current AABB.
  const slot = Math.round(binding.focus * 8) % 8
  const left = el.x
  const top = el.y
  const right = el.x + el.width
  const bottom = el.y + el.height
  switch (slot) {
    case 0:
      return { x: left, y: top }
    case 1:
      return { x: (left + right) / 2, y: top }
    case 2:
      return { x: right, y: top }
    case 3:
      return { x: right, y: (top + bottom) / 2 }
    case 4:
      return { x: right, y: bottom }
    case 5:
      return { x: (left + right) / 2, y: bottom }
    case 6:
      return { x: left, y: bottom }
    default:
      return { x: left, y: (top + bottom) / 2 }
  }
}
