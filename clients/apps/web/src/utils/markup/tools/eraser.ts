/**
 * Eraser tool — drag-to-delete elements under the cursor.
 *
 * Down: start a gesture, mark the element under the pointer (if any).
 * Move: as the cursor passes over each element, queue its id for
 *       deletion in the same transaction so the remote view sees the
 *       erase as one atomic update.
 * Up:   commit the queued ids via ``store.deleteMany`` (no-op if
 *       nothing was hit).
 *
 * Locked elements are skipped — the lock affordance protects against
 * accidental erasure as well as accidental move/resize.
 */

import type { CollabElement } from '../elements'
import type { Tool, ToolCtx } from './types'

interface EraseGesture {
  /** Ids queued for deletion this gesture. Insertion-ordered. */
  readonly queued: Set<string>
}

let gesture: EraseGesture | null = null

function isErasable(el: CollabElement | null): el is CollabElement {
  return el !== null && !el.locked
}

function tryQueue(ctx: ToolCtx, e: PointerEvent): void {
  if (!gesture) return
  const { x, y } = ctx.screenToWorld(e.clientX, e.clientY)
  const id = ctx.renderer.hitTest(x, y)
  if (id === null) return
  if (gesture.queued.has(id)) return
  if (!isErasable(ctx.store.get(id))) return
  gesture.queued.add(id)
}

export const eraserTool: Tool = {
  id: 'eraser',
  cursor: 'crosshair',

  onPointerDown(ctx, e) {
    gesture = { queued: new Set() }
    tryQueue(ctx, e)
  },

  onPointerMove(ctx, e) {
    tryQueue(ctx, e)
  },

  onPointerUp(ctx) {
    if (!gesture) return
    const ids = Array.from(gesture.queued)
    gesture = null
    if (ids.length === 0) return
    ctx.store.deleteMany(ids)
  },

  onCancel() {
    gesture = null
  },
}

/** Test-only accessor for the queued ids during an in-flight gesture. */
export function _eraserGestureSize(): number {
  return gesture ? gesture.queued.size : 0
}
