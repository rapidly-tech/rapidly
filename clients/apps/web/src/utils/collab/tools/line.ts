/**
 * Line drawing tool.
 *
 * Different interaction model than rect/ellipse/diamond. The drag
 * doesn't bound an AABB — the anchor is one endpoint and the cursor
 * is the other. We store both in ``points`` (element-local) and set
 * ``x / y / width / height`` to the axis-aligned bounding box of the
 * two points so the renderer's transform + the select tool's AABB
 * hit-testing still work.
 *
 * Shift constrains the segment to 0°, 45°, 90°. Alt does nothing —
 * "draw from centre" makes no sense for a two-point line.
 */

import type { Tool, ToolCtx } from './types'

const MIN_LENGTH = 4

interface DrawState {
  id: string
  anchorX: number
  anchorY: number
}

let state: DrawState | null = null

export const lineTool: Tool = {
  id: 'line',
  cursor: 'crosshair',

  onPointerDown(ctx, e) {
    const { x, y } = worldPoint(ctx, e)
    const id = ctx.store.create({
      type: 'line',
      x,
      y,
      width: 0,
      height: 0,
      points: [0, 0, 0, 0],
    })
    state = { id, anchorX: x, anchorY: y }
  },

  onPointerMove(ctx, e) {
    if (!state) return
    const { x, y } = worldPoint(ctx, e)
    ctx.store.update(state.id, computePatch(state, x, y, e.shiftKey))
  },

  onPointerUp(ctx) {
    if (!state) return
    const el = ctx.store.get(state.id)
    state = null
    if (!el || el.type !== 'line') return
    // Drop accidental taps — use the segment length, not the AABB
    // dimensions which can be zero for a horizontal/vertical line.
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
  return ctx.screenToWorld(e.clientX - rect.left, e.clientY - rect.top)
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
    // Snap to nearest 45° direction.
    const dx = endX - s.anchorX
    const dy = endY - s.anchorY
    const angle = Math.atan2(dy, dx)
    const snapped = Math.round(angle / (Math.PI / 4)) * (Math.PI / 4)
    const length = Math.hypot(dx, dy)
    endX = s.anchorX + Math.cos(snapped) * length
    endY = s.anchorY + Math.sin(snapped) * length
  }

  // AABB in world coords.
  const minX = Math.min(s.anchorX, endX)
  const minY = Math.min(s.anchorY, endY)
  const maxX = Math.max(s.anchorX, endX)
  const maxY = Math.max(s.anchorY, endY)
  const width = maxX - minX
  const height = maxY - minY

  // Element-local points: each endpoint offset from the AABB origin.
  const points = [s.anchorX - minX, s.anchorY - minY, endX - minX, endY - minY]

  return { x: minX, y: minY, width, height, points }
}
