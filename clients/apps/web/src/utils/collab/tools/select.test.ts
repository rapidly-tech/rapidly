/**
 * Select-tool tests — lean on a stub ctx so the tool exercises
 * real ElementStore + SelectionState without a canvas.
 *
 * The stub ``renderer.hitTest`` is programmable per-test so we can
 * simulate "click on element A" without needing a real isPointInPath.
 */

import { beforeEach, describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import { createElementStore, type ElementStore } from '../element-store'
import { SelectionState } from '../selection'
import { makeViewport, type Viewport } from '../viewport'
import type { SelectToolCtx } from './select'
import { currentMarqueeRect, selectTool } from './select'

function stubCtx(
  store: ElementStore,
  selection: SelectionState,
  hitTarget: string | null = null,
): SelectToolCtx {
  const viewport: Viewport = makeViewport()
  const renderer = {
    getViewport: () => viewport,
    setViewport: () => {},
    hitTest: () => hitTarget,
    screenToWorld: (x: number, y: number) => ({ x, y }),
    invalidate: () => {},
  } as unknown as SelectToolCtx['renderer']
  return {
    store,
    renderer,
    viewport,
    selection,
    screenToWorld: (x, y) => ({ x, y }),
    invalidate: () => {},
  }
}

function event(
  clientX: number,
  clientY: number,
  opts: { shift?: boolean } = {},
): PointerEvent {
  return {
    clientX,
    clientY,
    shiftKey: !!opts.shift,
    altKey: false,
    target: {
      getBoundingClientRect: () => ({ left: 0, top: 0 }),
    },
  } as unknown as PointerEvent
}

describe('selectTool', () => {
  beforeEach(() => {
    // Reset module-scope gesture state by running onCancel on a
    // throwaway ctx before each test.
    const doc = new Y.Doc()
    const s = new SelectionState()
    selectTool.onCancel?.(stubCtx(createElementStore(doc), s))
  })

  it('click on element replaces selection', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 100,
      height: 100,
      roundness: 0,
    })
    const sel = new SelectionState()
    const ctx = stubCtx(store, sel, a)

    selectTool.onPointerDown(ctx, event(50, 50))
    selectTool.onPointerUp(ctx, event(50, 50))
    expect(Array.from(sel.snapshot)).toEqual([a])
  })

  it('shift-click on element toggles membership', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 100,
      height: 100,
      roundness: 0,
    })
    const sel = new SelectionState()
    sel.add(a)
    const ctx = stubCtx(store, sel, a)

    selectTool.onPointerDown(ctx, event(50, 50, { shift: true }))
    selectTool.onPointerUp(ctx, event(50, 50, { shift: true }))
    expect(sel.has(a)).toBe(false)

    selectTool.onPointerDown(ctx, event(50, 50, { shift: true }))
    selectTool.onPointerUp(ctx, event(50, 50, { shift: true }))
    expect(sel.has(a)).toBe(true)
  })

  it('click on empty space with an existing selection clears it', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 100,
      height: 100,
      roundness: 0,
    })
    const sel = new SelectionState()
    sel.add(a)
    const ctx = stubCtx(store, sel, null)

    selectTool.onPointerDown(ctx, event(500, 500))
    selectTool.onPointerUp(ctx, event(500, 500))
    expect(sel.size).toBe(0)
  })

  it('drag from empty space marquees intersecting elements', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const inside = store.create({
      type: 'rect',
      x: 10,
      y: 10,
      width: 50,
      height: 50,
      roundness: 0,
    })
    const outside = store.create({
      type: 'rect',
      x: 500,
      y: 500,
      width: 50,
      height: 50,
      roundness: 0,
    })
    const sel = new SelectionState()
    const ctx = stubCtx(store, sel, null)

    selectTool.onPointerDown(ctx, event(0, 0))
    selectTool.onPointerMove(ctx, event(200, 200))
    // Marquee active now — verify the rect.
    const m = currentMarqueeRect()
    expect(m).toEqual({ x: 0, y: 0, width: 200, height: 200 })

    selectTool.onPointerUp(ctx, event(200, 200))
    const selected = Array.from(sel.snapshot).sort()
    expect(selected).toEqual([inside].sort())
    expect(selected).not.toContain(outside)
  })

  it('shift-marquee appends to existing selection', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 20,
      height: 20,
      roundness: 0,
    })
    const b = store.create({
      type: 'rect',
      x: 100,
      y: 100,
      width: 20,
      height: 20,
      roundness: 0,
    })
    const sel = new SelectionState()
    sel.add(a)
    const ctx = stubCtx(store, sel, null)

    selectTool.onPointerDown(ctx, event(80, 80, { shift: true }))
    selectTool.onPointerMove(ctx, event(200, 200))
    selectTool.onPointerUp(ctx, event(200, 200))
    expect(Array.from(sel.snapshot).sort()).toEqual([a, b].sort())
  })

  it('onCancel drops any in-progress marquee', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const sel = new SelectionState()
    const ctx = stubCtx(store, sel, null)
    selectTool.onPointerDown(ctx, event(0, 0))
    selectTool.onPointerMove(ctx, event(100, 100))
    expect(currentMarqueeRect()).not.toBeNull()
    selectTool.onCancel?.(ctx)
    expect(currentMarqueeRect()).toBeNull()
  })
})
