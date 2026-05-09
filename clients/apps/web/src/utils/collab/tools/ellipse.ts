/**
 * Ellipse drawing tool.
 *
 * Same drag-to-create UX as the rect tool; shares the shift-constrain
 * and alt-from-centre modifiers. Splitting the files rather than
 * parameterising one shared drawer keeps per-tool nuances (e.g. the
 * future arrow tool wiring endpoints to a shape) straightforward.
 */

import { snapPoint } from '../grid'
import { bboxFromElement, snapPointToObjects } from '../snap-to-objects'
import type { Tool, ToolCtx } from './types'

const MIN_DIMENSION = 4

interface DrawState {
  id: string
  anchorX: number
  anchorY: number
}

let state: DrawState | null = null

export const ellipseTool: Tool = {
  id: 'ellipse',
  cursor: 'crosshair',

  onPointerDown(ctx, e) {
    const { x, y } = worldPoint(ctx, e)
    const id = ctx.store.create({
      type: 'ellipse',
      x,
      y,
      width: 0,
      height: 0,
    })
    state = { id, anchorX: x, anchorY: y }
  },

  onPointerMove(ctx, e) {
    if (!state) return
    const { x, y } = worldPoint(ctx, e)
    const patch = computePatch(state, x, y, e.shiftKey, e.altKey)
    ctx.store.update(state.id, patch)
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
  let world = ctx.screenToWorld(e.clientX - rect.left, e.clientY - rect.top)
  if (ctx.renderer.isGridEnabled()) {
    world = snapPoint(world.x, world.y, ctx.renderer.getGridSize())
  }
  if (ctx.renderer.isSnapToObjectsEnabled() && !e.altKey) {
    const drawingId = state?.id
    const statics = ctx.store
      .list()
      .filter((el) => el.id !== drawingId)
      .map(bboxFromElement)
    if (statics.length > 0) {
      const snapped = snapPointToObjects(
        world,
        statics,
        ctx.renderer.getViewport().scale,
      )
      world = { x: snapped.x, y: snapped.y }
    }
  }
  return world
}

function computePatch(
  state: DrawState,
  worldX: number,
  worldY: number,
  shift: boolean,
  alt: boolean,
): { x: number; y: number; width: number; height: number } {
  let x = state.anchorX
  let y = state.anchorY
  let width = worldX - x
  let height = worldY - y

  if (shift) {
    const side = Math.max(Math.abs(width), Math.abs(height))
    width = Math.sign(width) * side || side
    height = Math.sign(height) * side || side
  }

  if (alt) {
    x = state.anchorX - width
    y = state.anchorY - height
    width = Math.abs(width) * 2
    height = Math.abs(height) * 2
  } else {
    if (width < 0) {
      x = state.anchorX + width
      width = -width
    }
    if (height < 0) {
      y = state.anchorY + height
      height = -height
    }
  }

  return { x, y, width, height }
}
