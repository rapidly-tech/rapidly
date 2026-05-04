/**
 * Arrow drawing tool.
 *
 * Two-point drag like the line tool plus a default end arrowhead.
 * Shift snaps to 0°/45°/90°.
 *
 * Phase 6a adds **snap-on-creation bindings**: if the pointer starts
 * or ends within ``BIND_RADIUS_PX`` of a bindable shape, the arrow
 * stores a ``{elementId, focus, gap}`` binding on the corresponding
 * endpoint. Phase 6b wires the inverse — moving / resizing the bound
 * shape updates the arrow endpoint in the same transaction.
 */

import type { ArrowBinding } from '../arrow-bindings'
import { findBinding, resolveBinding } from '../arrow-bindings'
import { snapPoint } from '../grid'
import {
  bboxFromElement,
  snapPointToObjects,
  snapToEdgeMidpoint,
} from '../snap-to-objects'
import type { Tool, ToolCtx } from './types'

const MIN_LENGTH = 4

interface DrawState {
  id: string
  anchorX: number
  anchorY: number
  /** Binding the arrow's *start* snapped to at creation. Locked in
   *  on pointer-down and never re-evaluated — users expect the
   *  anchor end to stay put once a drag begins. */
  startBinding: ArrowBinding | null
}

let state: DrawState | null = null

export const arrowTool: Tool = {
  id: 'arrow',
  cursor: 'crosshair',

  onPointerDown(ctx, e) {
    const { x, y } = worldPoint(ctx, e)
    const elements = ctx.store.list()
    const vp = ctx.renderer.getViewport()
    const startBinding = findBinding(elements, x, y, vp.scale)
    // If the start snaps to a shape, move our anchor to the exact
    // perimeter point so the arrow line doesn't jut inside the shape.
    let anchorX = x
    let anchorY = y
    if (startBinding) {
      const target = ctx.store.get(startBinding.elementId)
      if (target) {
        const p = resolveBinding(target, startBinding)
        anchorX = p.x
        anchorY = p.y
      }
    }
    const id = ctx.store.create({
      type: 'arrow',
      x: anchorX,
      y: anchorY,
      width: 0,
      height: 0,
      points: [0, 0, 0, 0],
      startArrowhead: null,
      endArrowhead: 'triangle',
      startBinding: startBinding ?? undefined,
    })
    state = { id, anchorX, anchorY, startBinding }
  },

  onPointerMove(ctx, e) {
    if (!state) return
    const { x, y } = worldPoint(ctx, e)
    const patch = computePatch(state, x, y, e.shiftKey)
    // Check whether the current cursor snaps to a bindable shape.
    // If so, pull the endpoint to the exact perimeter point and
    // record the binding. Exclude the arrow itself to avoid self-
    // bindings (the arrow IS in the store from pointer-down).
    const elements = ctx.store.list()
    const vp = ctx.renderer.getViewport()
    const endBinding = findBinding(elements, x, y, vp.scale, state.id)
    if (endBinding) {
      const target = ctx.store.get(endBinding.elementId)
      if (target) {
        const p = resolveBinding(target, endBinding)
        // Recompute patch so points + AABB reflect the snapped end.
        Object.assign(patch, computePatch(state, p.x, p.y, e.shiftKey))
      }
    }
    ctx.store.update(state.id, {
      ...patch,
      endBinding: endBinding ?? undefined,
    })
  },

  onPointerUp(ctx) {
    if (!state) return
    const el = ctx.store.get(state.id)
    state = null
    if (!el || el.type !== 'arrow') return
    const p = el.points
    if (p.length < 4) {
      ctx.store.delete(el.id)
      return
    }
    const dx = p[2] - p[0]
    const dy = p[3] - p[1]
    if (Math.hypot(dx, dy) < MIN_LENGTH) {
      ctx.store.delete(el.id)
    }
  },

  onCancel(ctx) {
    if (!state) return
    ctx.store.delete(state.id)
    state = null
  },
}

function worldPoint(ctx: ToolCtx, e: PointerEvent): { x: number; y: number } {
  const rect = (e.target as HTMLElement).getBoundingClientRect()
  let world = ctx.screenToWorld(e.clientX - rect.left, e.clientY - rect.top)
  if (ctx.renderer.isGridEnabled()) {
    world = snapPoint(world.x, world.y, ctx.renderer.getGridSize())
  }
  // Snap arrow endpoints to nearby element edges + centres. The
  // existing arrow-binding pass (``findBinding``) handles a different
  // contract — it locks the endpoint to a shape's anchor so a later
  // shape-move drags the endpoint along — whereas object snap just
  // pulls the cursor to a clean line. They compose cleanly: snap
  // happens here on the cursor, then ``findBinding`` consults the
  // (snapped) point on pointer-up. Skipped while alt is held.
  if (ctx.renderer.isSnapToObjectsEnabled() && !e.altKey) {
    const drawingId = state?.id
    const statics = ctx.store
      .list()
      .filter((el) => el.id !== drawingId)
      .map(bboxFromElement)
    if (statics.length > 0) {
      // Pass 1: per-axis snap to nearby element edges + centres so
      // the user gets the alignment-guide feel for arrow endpoints.
      const snapped = snapPointToObjects(
        world,
        statics,
        ctx.renderer.getViewport().scale,
      )
      world = { x: snapped.x, y: snapped.y }
      // Pass 2: 2-D edge-midpoint snap. When the cursor is close to
      // an exact edge midpoint or centre of a neighbour, pull both
      // axes to that anchor as a unit so the arrow lands cleanly on
      // the connection point.
      const mid = snapToEdgeMidpoint(
        world,
        statics,
        ctx.renderer.getViewport().scale,
      )
      if (mid) world = mid
    }
  }
  return world
}

function computePatch(
  s: DrawState,
  worldX: number,
  worldY: number,
  shift: boolean,
): {
  x: number
  y: number
  width: number
  height: number
  points: number[]
} {
  let endX = worldX
  let endY = worldY

  if (shift) {
    const dx = endX - s.anchorX
    const dy = endY - s.anchorY
    const angle = Math.atan2(dy, dx)
    const snapped = Math.round(angle / (Math.PI / 4)) * (Math.PI / 4)
    const length = Math.hypot(dx, dy)
    endX = s.anchorX + Math.cos(snapped) * length
    endY = s.anchorY + Math.sin(snapped) * length
  }

  const minX = Math.min(s.anchorX, endX)
  const minY = Math.min(s.anchorY, endY)
  const maxX = Math.max(s.anchorX, endX)
  const maxY = Math.max(s.anchorY, endY)
  const width = maxX - minX
  const height = maxY - minY

  const points = [s.anchorX - minX, s.anchorY - minY, endX - minX, endY - minY]

  return { x: minX, y: minY, width, height, points }
}
