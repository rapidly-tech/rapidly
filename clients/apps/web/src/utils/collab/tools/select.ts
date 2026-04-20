/**
 * Select tool.
 *
 * Behaviour
 * ---------
 * - Click an element → replace selection with that element.
 * - Shift-click an element → toggle it in the current selection.
 * - Click empty space → clear selection.
 * - Drag empty space → marquee. Every element whose AABB intersects
 *   the marquee is added on pointer-up. Shift during marquee appends
 *   to the existing selection; no shift replaces.
 *
 * Not-in-this-phase: drag-move of a selected element, resize handles,
 * rotation handle. Those land in Phase 4.
 */

import { isArrow, isFreeDraw, isLine } from '../elements'
import type { SelectionState } from '../selection'
import type { Tool, ToolCtx } from './types'

/** ``ToolCtx`` variant carrying the selection state. The select tool
 *  needs it; other tools don't, so we widen locally instead of
 *  polluting the base ``ToolCtx`` with a field most tools ignore. */
export interface SelectToolCtx extends ToolCtx {
  selection: SelectionState
}

interface GestureState {
  kind: 'click' | 'marquee'
  shift: boolean
  startWorldX: number
  startWorldY: number
  /** For marquee: current rect in world coords. */
  curX: number
  curY: number
  /** Selection snapshot at gesture start — used so shift-marquee
   *  appends without repeatedly re-adding on every pointer-move. */
  baseIds: ReadonlySet<string>
}

let state: GestureState | null = null

/** Minimum pointer travel (world units) to promote a click into a
 *  marquee. Anything below this registers as a plain click. */
const DRAG_THRESHOLD = 4

export const selectTool = {
  id: 'select',
  cursor: 'default',

  onPointerDown(ctx, e) {
    const sctx = ctx as SelectToolCtx
    const { x, y } = worldPoint(ctx, e)
    const hitId = sctx.renderer.hitTest(x, y)

    if (hitId) {
      // Click on an element: commit immediately — drag-to-move lands
      // in Phase 4, and we don't want a laggy "click" that only
      // registers on pointer-up.
      if (e.shiftKey) {
        sctx.selection.toggle(hitId)
      } else if (!sctx.selection.has(hitId)) {
        sctx.selection.set([hitId])
      }
      // Keep a pseudo-gesture open so pointer-up clears it cleanly.
      state = {
        kind: 'click',
        shift: e.shiftKey,
        startWorldX: x,
        startWorldY: y,
        curX: x,
        curY: y,
        baseIds: new Set(sctx.selection.snapshot),
      }
      return
    }

    // Empty-space: start a marquee. Don't clear the existing selection
    // yet — the user may release without dragging, and that's the
    // "deselect all" moment, OR they drag and we marquee.
    state = {
      kind: 'click',
      shift: e.shiftKey,
      startWorldX: x,
      startWorldY: y,
      curX: x,
      curY: y,
      baseIds: new Set(sctx.selection.snapshot),
    }
  },

  onPointerMove(ctx, e) {
    if (!state) return
    const sctx = ctx as SelectToolCtx
    const { x, y } = worldPoint(ctx, e)
    state.curX = x
    state.curY = y

    if (state.kind === 'click') {
      const dx = x - state.startWorldX
      const dy = y - state.startWorldY
      if (Math.hypot(dx, dy) >= DRAG_THRESHOLD) {
        state.kind = 'marquee'
        if (!state.shift) sctx.selection.clear()
      }
    }

    if (state.kind === 'marquee') {
      const rect = marqueeRect(state)
      const hits = elementsInRect(ctx, rect)
      const next = new Set(state.baseIds)
      for (const id of hits) next.add(id)
      sctx.selection.set(next)
      sctx.invalidate()
    }
  },

  onPointerUp(ctx, _e) {
    void _e
    if (!state) return
    const sctx = ctx as SelectToolCtx
    if (state.kind === 'click') {
      // The user clicked (no drag). If we didn't already commit in
      // onPointerDown (i.e. empty-space click with no shift), clear
      // the selection.
      const hitId = sctx.renderer.hitTest(state.startWorldX, state.startWorldY)
      if (!hitId && !state.shift) {
        sctx.selection.clear()
      }
    }
    state = null
    sctx.invalidate()
  },

  onCancel(ctx) {
    state = null
    ;(ctx as SelectToolCtx).invalidate()
  },
} as const satisfies Tool

/** Current marquee rect in world coords, or ``null`` when no marquee
 *  is active. Used by the selection overlay renderer. */
export function currentMarqueeRect(): {
  x: number
  y: number
  width: number
  height: number
} | null {
  if (!state || state.kind !== 'marquee') return null
  return marqueeRect(state)
}

function worldPoint(ctx: ToolCtx, e: PointerEvent): { x: number; y: number } {
  const rect = (e.target as HTMLElement).getBoundingClientRect()
  return ctx.screenToWorld(e.clientX - rect.left, e.clientY - rect.top)
}

/** The marquee rect in world space, normalised to positive w/h. */
function marqueeRect(s: GestureState): {
  x: number
  y: number
  width: number
  height: number
} {
  const x = Math.min(s.startWorldX, s.curX)
  const y = Math.min(s.startWorldY, s.curY)
  return {
    x,
    y,
    width: Math.abs(s.curX - s.startWorldX),
    height: Math.abs(s.curY - s.startWorldY),
  }
}

/** All element ids whose world-space AABB intersects ``rect``. Uses
 *  the element's (x, y, width, height) directly — a tight hit-test
 *  per shape is a nice-to-have but the perceptual cost is low. */
function elementsInRect(
  ctx: ToolCtx,
  rect: { x: number; y: number; width: number; height: number },
): string[] {
  const rx2 = rect.x + rect.width
  const ry2 = rect.y + rect.height
  const out: string[] = []
  for (const el of ctx.store.list()) {
    // Arrow/line/freedraw store a start point + local ``points``
    // array; their AABB comes from width/height set on creation —
    // adequate for marquee until Phase 5 lands free-form hit testing.
    const ex1 = el.x
    const ey1 = el.y
    const ex2 = el.x + el.width
    const ey2 = el.y + el.height
    if (ex2 < rect.x || ey2 < rect.y || ex1 > rx2 || ey1 > ry2) continue
    // Skip unimplemented shape types to match the renderer's policy
    // of silently dropping unknown elements.
    if (isArrow(el) || isLine(el) || isFreeDraw(el)) continue
    out.push(el.id)
  }
  return out
}
