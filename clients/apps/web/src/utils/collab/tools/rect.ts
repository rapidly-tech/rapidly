/**
 * Rect drawing tool.
 *
 * Pointer-down stamps a world-space anchor. Pointer-move commits a
 * rect with dimensions bounded by the two corners, tagged as the
 * in-progress element. Pointer-up finalises: any rect smaller than
 * ``MIN_DIMENSION`` world pixels is discarded as an accidental tap.
 *
 * The preview is rendered by the store itself (not a local shadow)
 * so the element exists in the CRDT from the first frame — remote
 * peers see the rect grow live, matching Excalidraw's shared-cursor
 * UX. Shift held constrains the rect to a square; Alt draws from
 * centre outward.
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

export const rectTool: Tool = {
  id: 'rect',
  cursor: 'crosshair',

  onPointerDown(ctx, e) {
    const { x, y } = worldPoint(ctx, e)
    const id = ctx.store.create({
      type: 'rect',
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
    // Abandoning the gesture should drop the half-drawn rect — a
    // user-visible "oh that appeared by accident" is worse than
    // silent discard.
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
  // Object snap pulls the in-progress corner toward nearby static
  // edges + centres. Skipped while drawing the very first element
  // (no static set) and when alt is held (Excalidraw escape hatch).
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
    // Constrain to a square — take the larger absolute dimension.
    const side = Math.max(Math.abs(width), Math.abs(height))
    width = Math.sign(width) * side || side
    height = Math.sign(height) * side || side
  }

  if (alt) {
    // Draw from centre out — double both dimensions and shift anchor.
    x = state.anchorX - width
    y = state.anchorY - height
    width = Math.abs(width) * 2
    height = Math.abs(height) * 2
  } else {
    // Normal: support dragging up/left by normalising to positive
    // dimensions and translating the anchor.
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
