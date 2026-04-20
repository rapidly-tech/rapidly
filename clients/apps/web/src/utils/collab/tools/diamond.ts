/**
 * Diamond drawing tool.
 *
 * Identical drag-to-create UX to rect/ellipse. Extracted rather than
 * parameterising the rect tool so per-shape nuances (roundness,
 * aspect-lock, later alt/shift modifiers) can diverge without a
 * shared "draw an AABB and commit" abstraction leaking across them.
 */

import type { Tool, ToolCtx } from './types'

const MIN_DIMENSION = 4

interface DrawState {
  id: string
  anchorX: number
  anchorY: number
}

let state: DrawState | null = null

export const diamondTool: Tool = {
  id: 'diamond',
  cursor: 'crosshair',

  onPointerDown(ctx, e) {
    const { x, y } = worldPoint(ctx, e)
    const id = ctx.store.create({
      type: 'diamond',
      x,
      y,
      width: 0,
      height: 0,
      roundness: 0,
    })
    state = { id, anchorX: x, anchorY: y }
  },

  onPointerMove(ctx, e) {
    if (!state) return
    const { x, y } = worldPoint(ctx, e)
    ctx.store.update(state.id, computePatch(state, x, y, e.shiftKey, e.altKey))
  },

  onPointerUp(ctx) {
    if (!state) return
    const el = ctx.store.get(state.id)
    state = null
    if (!el) return
    if (el.width < MIN_DIMENSION || el.height < MIN_DIMENSION) {
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
  alt: boolean,
): { x: number; y: number; width: number; height: number } {
  let x = s.anchorX
  let y = s.anchorY
  let width = worldX - x
  let height = worldY - y

  if (shift) {
    const side = Math.max(Math.abs(width), Math.abs(height))
    width = Math.sign(width) * side || side
    height = Math.sign(height) * side || side
  }

  if (alt) {
    x = s.anchorX - width
    y = s.anchorY - height
    width = Math.abs(width) * 2
    height = Math.abs(height) * 2
  } else {
    if (width < 0) {
      x = s.anchorX + width
      width = -width
    }
    if (height < 0) {
      y = s.anchorY + height
      height = -height
    }
  }

  return { x, y, width, height }
}
