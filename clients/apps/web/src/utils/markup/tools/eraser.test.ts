/**
 * Eraser tool — pinned behaviour:
 *
 * - Drag-over deletes the elements under the cursor (commit on up).
 * - Locked elements are skipped (lock guard mirrors select tool's
 *   delete-key handling).
 * - The same element is never queued twice in one gesture.
 * - Cancel discards the queue (no store mutation).
 */

import { beforeEach, describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import { createElementStore, type ElementStore } from '../element-store'
import { makeViewport, type Viewport } from '../viewport'
import { _eraserGestureSize, eraserTool } from './eraser'
import type { ToolCtx } from './types'

interface FakeRenderer {
  hits: Map<string, string>
  getViewport(): Viewport
  setViewport(): void
  hitTest(x: number, y: number): string | null
}

function stubCtx(store: ElementStore): {
  ctx: ToolCtx
  renderer: FakeRenderer
} {
  const viewport: Viewport = makeViewport()
  const renderer: FakeRenderer = {
    hits: new Map(),
    getViewport: () => viewport,
    setViewport: () => {},
    hitTest(x, y) {
      return renderer.hits.get(`${x},${y}`) ?? null
    },
  }
  const ctx: ToolCtx = {
    store,
    renderer: renderer as unknown as ToolCtx['renderer'],
    viewport,
    screenToWorld: (x, y) => ({ x, y }),
    invalidate: () => {},
  }
  return { ctx, renderer }
}

function evt(x: number, y: number): PointerEvent {
  return { clientX: x, clientY: y } as unknown as PointerEvent
}

describe('eraserTool', () => {
  let store: ElementStore
  beforeEach(() => {
    const doc = new Y.Doc()
    store = createElementStore(doc)
    store.create({
      id: 'a',
      type: 'rect',
      x: 0,
      y: 0,
      width: 50,
      height: 50,
    })
    store.create({
      id: 'b',
      type: 'rect',
      x: 100,
      y: 0,
      width: 50,
      height: 50,
    })
    store.create({
      id: 'locked',
      type: 'rect',
      x: 200,
      y: 0,
      width: 50,
      height: 50,
      locked: true,
    })
  })

  it('deletes the element under the cursor on commit', () => {
    const { ctx, renderer } = stubCtx(store)
    renderer.hits.set('25,25', 'a')

    eraserTool.onPointerDown(ctx, evt(25, 25))
    eraserTool.onPointerUp(ctx, evt(25, 25))

    expect(store.get('a')).toBeNull()
    expect(store.get('b')).not.toBeNull()
  })

  it('queues multiple ids during drag and deletes them atomically', () => {
    const { ctx, renderer } = stubCtx(store)
    renderer.hits.set('25,25', 'a')
    renderer.hits.set('125,25', 'b')

    eraserTool.onPointerDown(ctx, evt(25, 25))
    eraserTool.onPointerMove(ctx, evt(125, 25))
    expect(_eraserGestureSize()).toBe(2)
    eraserTool.onPointerUp(ctx, evt(125, 25))

    expect(store.get('a')).toBeNull()
    expect(store.get('b')).toBeNull()
  })

  it('does not delete locked elements', () => {
    const { ctx, renderer } = stubCtx(store)
    renderer.hits.set('225,25', 'locked')

    eraserTool.onPointerDown(ctx, evt(225, 25))
    eraserTool.onPointerUp(ctx, evt(225, 25))

    expect(store.get('locked')).not.toBeNull()
  })

  it('does not double-queue the same id mid-drag', () => {
    const { ctx, renderer } = stubCtx(store)
    renderer.hits.set('25,25', 'a')
    renderer.hits.set('30,30', 'a')

    eraserTool.onPointerDown(ctx, evt(25, 25))
    eraserTool.onPointerMove(ctx, evt(30, 30))
    expect(_eraserGestureSize()).toBe(1)
    eraserTool.onPointerUp(ctx, evt(30, 30))
  })

  it('cancel discards the queue without mutating the store', () => {
    const { ctx, renderer } = stubCtx(store)
    renderer.hits.set('25,25', 'a')

    eraserTool.onPointerDown(ctx, evt(25, 25))
    eraserTool.onCancel?.(ctx)
    eraserTool.onPointerUp(ctx, evt(25, 25))

    expect(store.get('a')).not.toBeNull()
    expect(_eraserGestureSize()).toBe(0)
  })

  it('skips when no element is under the cursor', () => {
    const { ctx } = stubCtx(store)
    eraserTool.onPointerDown(ctx, evt(500, 500))
    eraserTool.onPointerUp(ctx, evt(500, 500))
    expect(store.get('a')).not.toBeNull()
    expect(store.get('b')).not.toBeNull()
  })
})
