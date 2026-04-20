/**
 * Arrow drawing tool.
 *
 * Two-point drag like the line tool, but the element ships with a
 * default end arrowhead. Shift snaps to 0°/45°/90°. Arrow bindings
 * (endpoint snap to another shape's anchor) land in Phase 6; this
 * tool leaves the ``startBinding`` / ``endBinding`` fields unset.
 */

import type { Tool, ToolCtx } from './types'

const MIN_LENGTH = 4

interface DrawState {
  id: string
  anchorX: number
  anchorY: number
}

let state: DrawState | null = null

export const arrowTool: Tool = {
  id: 'arrow',
  cursor: 'crosshair',

  onPointerDown(ctx, e) {
    const { x, y } = worldPoint(ctx, e)
    const id = ctx.store.create({
      type: 'arrow',
      x,
      y,
      width: 0,
      height: 0,
      points: [0, 0, 0, 0],
      startArrowhead: null,
      endArrowhead: 'triangle',
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
