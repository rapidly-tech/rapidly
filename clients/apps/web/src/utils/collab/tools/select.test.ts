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
    isGridEnabled: () => false,
    getGridSize: () => 20,
    isSnapToObjectsEnabled: () => false,
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

  it('drag on a selected element moves the whole selection', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create({
      type: 'rect',
      x: 10,
      y: 10,
      width: 100,
      height: 50,
      roundness: 0,
    })
    const b = store.create({
      type: 'rect',
      x: 200,
      y: 50,
      width: 40,
      height: 40,
      roundness: 0,
    })
    const sel = new SelectionState()
    sel.set([a, b])
    const ctx = stubCtx(store, sel, a)

    selectTool.onPointerDown(ctx, event(30, 30))
    // Under the drag threshold — still a click.
    selectTool.onPointerMove(ctx, event(32, 32))
    expect(store.get(a)?.x).toBe(10)

    // Promote to move.
    selectTool.onPointerMove(ctx, event(80, 60))
    // +50 on x, +30 on y applied to both anchors.
    expect(store.get(a)?.x).toBe(60)
    expect(store.get(a)?.y).toBe(40)
    expect(store.get(b)?.x).toBe(250)
    expect(store.get(b)?.y).toBe(80)

    selectTool.onPointerUp(ctx, event(80, 60))
    // Final committed position.
    expect(store.get(a)?.x).toBe(60)
    expect(store.get(b)?.y).toBe(80)
  })

  it('onCancel rolls back an in-progress move', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create({
      type: 'rect',
      x: 10,
      y: 20,
      width: 50,
      height: 50,
      roundness: 0,
    })
    const sel = new SelectionState()
    sel.set([a])
    const ctx = stubCtx(store, sel, a)

    selectTool.onPointerDown(ctx, event(30, 40))
    selectTool.onPointerMove(ctx, event(80, 90))
    // Mid-flight: element moved.
    expect(store.get(a)?.x).not.toBe(10)

    selectTool.onCancel?.(ctx)
    // Back at the anchor.
    expect(store.get(a)?.x).toBe(10)
    expect(store.get(a)?.y).toBe(20)
  })

  it('snaps drag deltas to the grid when the renderer reports it enabled', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 50,
      height: 50,
      roundness: 0,
    })
    const sel = new SelectionState()
    sel.set([a])
    const ctx = stubCtx(store, sel, a)
    ;(ctx.renderer as { isGridEnabled: () => boolean }).isGridEnabled = () =>
      true

    selectTool.onPointerDown(ctx, event(10, 10))
    // Drag delta (49, 31) → snaps to (40, 40) at gridSize 20.
    selectTool.onPointerMove(ctx, event(59, 41))
    expect(store.get(a)?.x).toBe(40)
    expect(store.get(a)?.y).toBe(40)
    selectTool.onPointerUp(ctx, event(59, 41))
  })

  it('snaps to a sibling element s edges when snap-to-objects is on', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const dragger = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 50,
      height: 50,
      roundness: 0,
    })
    // Sibling whose left edge is at x=100. Dragging dragger 99 px →
    // its left would land at 99; snap should pull it to 100.
    store.create({
      type: 'rect',
      x: 100,
      y: 1000, // far on y so y-axis can't snap
      width: 50,
      height: 50,
      roundness: 0,
    })
    const sel = new SelectionState()
    sel.set([dragger])
    const ctx = stubCtx(store, sel, dragger)
    ;(
      ctx.renderer as { isSnapToObjectsEnabled: () => boolean }
    ).isSnapToObjectsEnabled = () => true

    selectTool.onPointerDown(ctx, event(10, 10))
    selectTool.onPointerMove(ctx, event(109, 11))
    expect(store.get(dragger)?.x).toBe(100)
    selectTool.onPointerUp(ctx, event(109, 11))
  })

  it('click on an unselected element replaces selection before drag-move', () => {
    // User has A selected; clicks B (not held shift); drags.
    // Expected: selection becomes just B, drag moves B only.
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create({
      type: 'rect',
      x: 10,
      y: 10,
      width: 50,
      height: 50,
      roundness: 0,
    })
    const b = store.create({
      type: 'rect',
      x: 200,
      y: 10,
      width: 50,
      height: 50,
      roundness: 0,
    })
    const sel = new SelectionState()
    sel.set([a])
    const ctx = stubCtx(store, sel, b)

    selectTool.onPointerDown(ctx, event(220, 30))
    selectTool.onPointerMove(ctx, event(260, 50))
    expect(Array.from(sel.snapshot)).toEqual([b])
    expect(store.get(b)?.x).toBe(240)
    expect(store.get(a)?.x).toBe(10)
    selectTool.onPointerUp(ctx, event(260, 50))
  })
})
