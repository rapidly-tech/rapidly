/**
 * Lasso tool — free-form area selection.
 *
 * Pointer-down begins a closed polygon; every pointer-move appends a
 * new vertex (downsampled to keep the path responsive at any scale);
 * pointer-up turns the polygon into a selection by point-in-polygon
 * testing each element's centre.
 *
 * Differs from the select tool's marquee:
 *
 *   - **Marquee** is an axis-aligned rectangle from the drag's
 *     start/end points.
 *   - **Lasso** is the user's freehand outline. Same intent (collect
 *     a region of elements) but lets the user dodge intervening
 *     shapes the marquee would inadvertently catch.
 *
 * Hit semantics: an element is included when its centre point lies
 * inside the closed polygon. Centre-point is the simplest defensible
 * rule and avoids flicker as the user drags through partial overlaps.
 *
 * Shift modifier: Shift held on pointer-down appends to the existing
 * selection; otherwise the new lasso replaces it. Mirrors the marquee
 * convention.
 *
 * The tool exposes ``currentLassoPath()`` so the selection overlay can
 * paint the in-progress polygon. Pattern matches ``currentMarqueeRect``
 * in ``select.ts``.
 */

import { expandToGroups } from '../groups'
import type { SelectionState } from '../selection'
import type { Tool, ToolCtx } from './types'

interface LassoState {
  shift: boolean
  /** Snapshot of the selection at gesture start, used as the base
   *  set when shift is held so we add to (not reset) it on each move. */
  baseIds: ReadonlySet<string>
  /** Polygon vertices in world coords. Flat ``[x0,y0,x1,y1,…]`` so
   *  the renderer can paint without re-allocating per frame. */
  points: number[]
}

let state: LassoState | null = null

/** Minimum world-space distance between two consecutive lasso points.
 *  Stops a slow pointer move from generating thousands of near-
 *  duplicate vertices and keeps the point-in-polygon scan cheap. */
const POINT_SPACING = 4

export interface LassoToolCtx extends ToolCtx {
  selection: SelectionState
}

export const lassoTool: Tool = {
  id: 'lasso',
  cursor: 'crosshair',

  onPointerDown(ctx, e) {
    const sctx = ctx as LassoToolCtx
    const { x, y } = worldPoint(ctx, e)
    state = {
      shift: e.shiftKey,
      baseIds: e.shiftKey
        ? new Set(sctx.selection.snapshot)
        : (new Set() as ReadonlySet<string>),
      points: [x, y],
    }
    if (!e.shiftKey) sctx.selection.clear()
    ctx.invalidate()
  },

  onPointerMove(ctx, e) {
    if (!state) return
    const { x, y } = worldPoint(ctx, e)
    const last = state.points.length
    const lx = state.points[last - 2]
    const ly = state.points[last - 1]
    if (Math.hypot(x - lx, y - ly) < POINT_SPACING) return
    state.points.push(x, y)

    // Live preview: recompute the selection on every appended vertex
    // so the user sees what the lasso has caught so far. Group expansion
    // is applied so dragging across one member of a group selects the
    // whole group atomically — same rule the marquee enforces.
    const sctx = ctx as LassoToolCtx
    const ids = new Set(state.baseIds)
    for (const id of elementsInsidePolygon(ctx, state.points)) ids.add(id)
    sctx.selection.set(expandToGroups(ctx.store, ids))
    ctx.invalidate()
  },

  onPointerUp(ctx) {
    if (!state) return
    state = null
    ctx.invalidate()
  },

  onCancel(ctx) {
    state = null
    ctx.invalidate()
  },
}

/** Vertices of the in-progress lasso polygon in world coords, or
 *  ``null`` when no gesture is active. The selection overlay reads
 *  this every paint so the polygon traces the user's pointer in
 *  real time. */
export function currentLassoPath(): readonly number[] | null {
  if (!state) return null
  return state.points
}

/** Reset the module-level state. Tests use this between cases so a
 *  cancelled gesture from one test doesn't leak into the next. Not
 *  exported in the index — the Tool's ``onCancel`` is the production
 *  path. */
export function _resetLassoStateForTests(): void {
  state = null
}

// ── Internals ────────────────────────────────────────────────────────

function worldPoint(ctx: ToolCtx, e: PointerEvent): { x: number; y: number } {
  const rect = (e.target as HTMLElement).getBoundingClientRect()
  return ctx.screenToWorld(e.clientX - rect.left, e.clientY - rect.top)
}

/** Find every element whose centre point lies inside the polygon.
 *  Polygon is flat ``[x0,y0,x1,y1,…]`` and treated as closed (last
 *  vertex implicitly connects to the first). Caller is responsible
 *  for filtering locked elements if needed. */
export function elementsInsidePolygon(
  ctx: ToolCtx,
  poly: readonly number[],
): string[] {
  if (poly.length < 6) return [] // need at least 3 vertices
  const out: string[] = []
  for (const el of ctx.store.list()) {
    const cx = el.x + el.width / 2
    const cy = el.y + el.height / 2
    if (pointInPolygon(cx, cy, poly)) out.push(el.id)
  }
  return out
}

/** Crossing-number point-in-polygon test. ``poly`` is flat
 *  ``[x0,y0,x1,y1,…]``; returns ``true`` when ``(x, y)`` is strictly
 *  inside or on the boundary. Self-intersecting polygons follow the
 *  even-odd rule, which matches what users intuitively expect when
 *  they cross their own lasso path. */
export function pointInPolygon(
  x: number,
  y: number,
  poly: readonly number[],
): boolean {
  const n = poly.length / 2
  if (n < 3) return false
  let inside = false
  let j = n - 1
  for (let i = 0; i < n; i++) {
    const xi = poly[i * 2]
    const yi = poly[i * 2 + 1]
    const xj = poly[j * 2]
    const yj = poly[j * 2 + 1]
    const intersect =
      yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi || 1e-9) + xi
    if (intersect) inside = !inside
    j = i
  }
  return inside
}
