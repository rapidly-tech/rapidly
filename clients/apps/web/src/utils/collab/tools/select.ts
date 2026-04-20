/**
 * Select tool.
 *
 * Behaviour
 * ---------
 * - Click an element → replace selection with that element.
 * - Shift-click an element → toggle it in the current selection.
 * - Click empty space → clear selection.
 * - **Drag a selected element → move the whole selection** (Phase 4a).
 * - Drag empty space → marquee. Every element whose AABB intersects
 *   the marquee is added on pointer-up. Shift during marquee appends
 *   to the existing selection; no shift replaces.
 *
 * Not-in-this-phase: resize handles, rotation handle. Those land in
 * Phase 4b.
 */

import { collectBoundArrowPatches } from '../arrow-bindings'

// Every element now has a rendered adapter, so marquee can include
// all of them. Future unimplemented types (text/sticky/image/frame/
// embed) will be filtered here when they land.
import {
  anchorFrom,
  applyResize,
  cursorForHandle,
  hitHandle,
  rotatePoint,
  type HandleId,
  type ResizeAnchor,
} from '../resize'
import type { SelectionState } from '../selection'
import type { Tool, ToolCtx } from './types'

/** ``ToolCtx`` variant carrying the selection state. The select tool
 *  needs it; other tools don't, so we widen locally instead of
 *  polluting the base ``ToolCtx`` with a field most tools ignore. */
export interface SelectToolCtx extends ToolCtx {
  selection: SelectionState
}

type GestureKind = 'click' | 'marquee' | 'moving' | 'resizing'

interface GestureState {
  kind: GestureKind
  shift: boolean
  startWorldX: number
  startWorldY: number
  /** For marquee: current rect in world coords. */
  curX: number
  curY: number
  /** Selection snapshot at gesture start. marquee uses it as a base
   *  so shift-marquee appends; moving uses it to know *which* ids to
   *  translate. */
  baseIds: ReadonlySet<string>
  /** For moving: original (x, y) of each selected element at gesture
   *  start. Drag deltas are applied against these snapshots so a
   *  micro-drift per pointermove doesn't accumulate floating-point
   *  error. */
  moveAnchors?: Map<string, { x: number; y: number }>
  /** For resizing: the id + bounding-box snapshot + which handle the
   *  user grabbed. Only set when ``kind === 'resizing'``. */
  resizeId?: string
  resizeAnchor?: ResizeAnchor
  resizeHandle?: HandleId
}

let state: GestureState | null = null

/** Minimum pointer travel (world units) to promote a click into a
 *  marquee or a move. Anything below this registers as a plain click. */
const DRAG_THRESHOLD = 4

export const selectTool = {
  id: 'select',
  cursor: 'default',

  onPointerDown(ctx, e) {
    const sctx = ctx as SelectToolCtx
    const { x, y } = worldPoint(ctx, e)

    // Check resize handles first — handles sit on top of their element
    // and the user expects clicking one to start a resize, even when
    // the pointer technically lands outside the element's bounds
    // (the handle juts out slightly).
    if (sctx.selection.size === 1) {
      const [id] = sctx.selection.snapshot
      const el = ctx.store.get(id)
      if (el) {
        const rect = (e.target as HTMLElement).getBoundingClientRect()
        const screenX = e.clientX - rect.left
        const screenY = e.clientY - rect.top
        const handle = hitHandle(
          el,
          ctx.renderer.getViewport(),
          screenX,
          screenY,
        )
        if (handle) {
          state = {
            kind: 'resizing',
            shift: e.shiftKey,
            startWorldX: x,
            startWorldY: y,
            curX: x,
            curY: y,
            baseIds: new Set(sctx.selection.snapshot),
            resizeId: id,
            resizeAnchor: anchorFrom(el),
            resizeHandle: handle,
          }
          return
        }
      }
    }

    const hitId = sctx.renderer.hitTest(x, y)

    if (hitId) {
      // Shift-click: toggle membership and stay in click state (no
      // move) — shift-drag-move is useful but out of scope for 4a.
      if (e.shiftKey) {
        sctx.selection.toggle(hitId)
        state = clickState(x, y, true, sctx.selection.snapshot)
        return
      }

      // Plain click / plain click-drag: if the hit element isn't yet
      // selected, replace the selection with it first. Then arm a
      // move gesture — promoted on drag threshold.
      if (!sctx.selection.has(hitId)) {
        sctx.selection.set([hitId])
      }
      state = clickState(x, y, false, sctx.selection.snapshot)
      return
    }

    // Empty-space: start a click (may promote to marquee).
    state = clickState(x, y, e.shiftKey, sctx.selection.snapshot)
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
        // Decide which gesture we're in: if every base id is in the
        // live selection AND we started on a hit, promote to move;
        // otherwise promote to marquee.
        const startedOnHit = sctx.renderer.hitTest(
          state.startWorldX,
          state.startWorldY,
        )
        if (
          startedOnHit &&
          state.baseIds.size > 0 &&
          state.baseIds.has(startedOnHit)
        ) {
          state.kind = 'moving'
          const anchors = new Map<string, { x: number; y: number }>()
          for (const id of state.baseIds) {
            const el = ctx.store.get(id)
            if (el) anchors.set(id, { x: el.x, y: el.y })
          }
          state.moveAnchors = anchors
        } else {
          state.kind = 'marquee'
          if (!state.shift) sctx.selection.clear()
        }
      }
    }

    if (state.kind === 'marquee') {
      const rect = marqueeRect(state)
      const hits = elementsInRect(ctx, rect)
      const next = new Set(state.baseIds)
      for (const id of hits) next.add(id)
      sctx.selection.set(next)
      sctx.invalidate()
      return
    }

    if (state.kind === 'moving' && state.moveAnchors) {
      const dx = x - state.startWorldX
      const dy = y - state.startWorldY
      const patches: { id: string; patch: Record<string, unknown> }[] = []
      for (const [id, anchor] of state.moveAnchors) {
        patches.push({ id, patch: { x: anchor.x + dx, y: anchor.y + dy } })
      }
      if (patches.length > 0) {
        // Apply the move first, then compute bound-arrow patches
        // against the just-written state. One transaction so remote
        // peers see a single frame; the store already wraps each
        // updateMany in a transaction, and inside the same tick a
        // second updateMany appends to the same Yjs transaction by
        // the scheduler.
        ctx.store.updateMany(patches)
        const changed = new Set<string>()
        for (const p of patches) changed.add(p.id)
        const arrowPatches = collectBoundArrowPatches(ctx.store.list(), changed)
        if (arrowPatches.length > 0) ctx.store.updateMany(arrowPatches)
      }
      sctx.invalidate()
      return
    }

    if (
      state.kind === 'resizing' &&
      state.resizeId &&
      state.resizeAnchor &&
      state.resizeHandle
    ) {
      // Un-rotate the drag delta around the element's centre before
      // applying — our applyResize math is in the element's own
      // axis-aligned frame.
      const a = state.resizeAnchor
      const cx = a.x + a.width / 2
      const cy = a.y + a.height / 2
      const startLocal = rotatePoint(
        state.startWorldX,
        state.startWorldY,
        cx,
        cy,
        -a.angle,
      )
      const curLocal = rotatePoint(x, y, cx, cy, -a.angle)
      const dx = curLocal.x - startLocal.x
      const dy = curLocal.y - startLocal.y
      const next = applyResize(a, state.resizeHandle, dx, dy)
      ctx.store.update(state.resizeId, next)
      const arrowPatches = collectBoundArrowPatches(
        ctx.store.list(),
        new Set([state.resizeId]),
      )
      if (arrowPatches.length > 0) ctx.store.updateMany(arrowPatches)
      sctx.invalidate()
    }
  },

  onPointerUp(ctx, _e) {
    void _e
    if (!state) return
    const sctx = ctx as SelectToolCtx
    if (state.kind === 'click') {
      // No drag. If we clicked empty space without shift, clear the
      // selection — the pointer-down left it intact in case this was
      // a drag that never drifted past the threshold.
      const hitId = sctx.renderer.hitTest(state.startWorldX, state.startWorldY)
      if (!hitId && !state.shift) {
        sctx.selection.clear()
      }
    }
    state = null
    sctx.invalidate()
  },

  onCancel(ctx) {
    const sctx = ctx as SelectToolCtx
    if (state?.kind === 'moving' && state.moveAnchors) {
      // Roll the elements back to their anchors so a cancelled drag
      // doesn't leave them mid-flight. Cheap — the CRDT sees a single
      // updateMany reversing the move.
      const patches: { id: string; patch: { x: number; y: number } }[] = []
      for (const [id, anchor] of state.moveAnchors) {
        patches.push({ id, patch: { x: anchor.x, y: anchor.y } })
      }
      if (patches.length > 0) ctx.store.updateMany(patches)
    }
    if (state?.kind === 'resizing' && state.resizeId && state.resizeAnchor) {
      const a = state.resizeAnchor
      ctx.store.update(state.resizeId, {
        x: a.x,
        y: a.y,
        width: a.width,
        height: a.height,
      })
    }
    state = null
    sctx.invalidate()
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

/** CSS cursor appropriate for the pointer's current screen location
 *  over the canvas. Returns the directional resize cursor when over a
 *  handle on a single-selected element; otherwise the tool's default.
 *
 *  The demo page wires this into ``onPointerMove`` so hovering a
 *  handle swaps the cursor without needing a full mini state machine. */
export function hoverCursor(
  ctx: SelectToolCtx,
  screenX: number,
  screenY: number,
  defaultCursor: string,
): string {
  if (ctx.selection.size !== 1) return defaultCursor
  const [id] = ctx.selection.snapshot
  const el = ctx.store.get(id)
  if (!el) return defaultCursor
  const handle = hitHandle(el, ctx.renderer.getViewport(), screenX, screenY)
  return handle ? cursorForHandle(handle) : defaultCursor
}

function clickState(
  x: number,
  y: number,
  shift: boolean,
  baseIds: ReadonlySet<string>,
): GestureState {
  return {
    kind: 'click',
    shift,
    startWorldX: x,
    startWorldY: y,
    curX: x,
    curY: y,
    baseIds: new Set(baseIds),
  }
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
    const ex1 = el.x
    const ey1 = el.y
    const ex2 = el.x + el.width
    const ey2 = el.y + el.height
    if (ex2 < rect.x || ey2 < rect.y || ex1 > rx2 || ey1 > ry2) continue
    out.push(el.id)
  }
  return out
}
