import { describe, expect, it, vi } from 'vitest'
import * as Y from 'yjs'

import { createElementStore } from './element-store'
import { SelectionState } from './selection'
import { makeSelectionOverlay } from './selection-overlay'
import { makeViewport } from './viewport'

/** Mock 2D context that records every method + property write the
 *  selection overlay actually uses. Scalar props are captured as an
 *  ordered log so we can assert "stroke colour was grey *just before*
 *  the stroke call" for locked elements. */
function mockCtx() {
  const strokeStyleLog: string[] = []
  const fillStyleLog: string[] = []
  const lineDashLog: number[][] = []
  const inner = {
    save: vi.fn(),
    restore: vi.fn(),
    translate: vi.fn(),
    rotate: vi.fn(),
    strokeRect: vi.fn(),
    fillRect: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    quadraticCurveTo: vi.fn(),
    closePath: vi.fn(),
    fill: vi.fn(),
    stroke: vi.fn(),
    arc: vi.fn(),
    setLineDash: vi.fn((pattern: number[]) => {
      lineDashLog.push([...pattern])
    }),
    lineWidth: 0,
  }
  Object.defineProperty(inner, 'strokeStyle', {
    set(v: string) {
      strokeStyleLog.push(v)
    },
    get() {
      return strokeStyleLog[strokeStyleLog.length - 1] ?? ''
    },
    configurable: true,
  })
  Object.defineProperty(inner, 'fillStyle', {
    set(v: string) {
      fillStyleLog.push(v)
    },
    get() {
      return fillStyleLog[fillStyleLog.length - 1] ?? ''
    },
    configurable: true,
  })
  return {
    ctx: inner as unknown as CanvasRenderingContext2D,
    inner: inner as unknown as {
      save: ReturnType<typeof vi.fn>
      restore: ReturnType<typeof vi.fn>
      translate: ReturnType<typeof vi.fn>
      rotate: ReturnType<typeof vi.fn>
      strokeRect: ReturnType<typeof vi.fn>
      fillRect: ReturnType<typeof vi.fn>
      setLineDash: ReturnType<typeof vi.fn>
      beginPath: ReturnType<typeof vi.fn>
      arc: ReturnType<typeof vi.fn>
      fill: ReturnType<typeof vi.fn>
      stroke: ReturnType<typeof vi.fn>
    },
    strokeStyleLog,
    fillStyleLog,
    lineDashLog,
  }
}

function freshStore() {
  const doc = new Y.Doc()
  const store = createElementStore(doc)
  return { doc, store }
}

describe('makeSelectionOverlay', () => {
  it('is a no-op when nothing is selected and no marquee is active', () => {
    const { store } = freshStore()
    const selection = new SelectionState()
    const paint = makeSelectionOverlay({
      store,
      selection,
      getMarquee: () => null,
      getViewport: () => makeViewport(),
    })
    const m = mockCtx()
    paint(m.ctx)
    expect(m.inner.strokeRect).not.toHaveBeenCalled()
    expect(m.inner.fillRect).not.toHaveBeenCalled()
  })

  it('fills + strokes the marquee rect when one is active', () => {
    const { store } = freshStore()
    const selection = new SelectionState()
    const paint = makeSelectionOverlay({
      store,
      selection,
      getMarquee: () => ({ x: 10, y: 20, width: 100, height: 50 }),
      getViewport: () => makeViewport(),
    })
    const m = mockCtx()
    paint(m.ctx)
    expect(m.inner.fillRect).toHaveBeenCalledWith(10, 20, 100, 50)
    expect(m.inner.strokeRect).toHaveBeenCalledWith(10, 20, 100, 50)
  })

  it('skips degenerate zero-size marquees', () => {
    const { store } = freshStore()
    const selection = new SelectionState()
    const paint = makeSelectionOverlay({
      store,
      selection,
      getMarquee: () => ({ x: 10, y: 20, width: 0, height: 50 }),
      getViewport: () => makeViewport(),
    })
    const m = mockCtx()
    paint(m.ctx)
    expect(m.inner.fillRect).not.toHaveBeenCalled()
  })

  it('strokes bounds + 8 handles for a single-element selection', () => {
    const { store } = freshStore()
    const id = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 100,
      height: 60,
    })
    const selection = new SelectionState()
    selection.set([id])
    const paint = makeSelectionOverlay({
      store,
      selection,
      getMarquee: () => null,
      getViewport: () => makeViewport(),
    })
    const m = mockCtx()
    paint(m.ctx)
    // 1 bounds strokeRect + 8 handle strokeRects = 9.
    expect(m.inner.strokeRect).toHaveBeenCalledTimes(9)
    // Handles are filled white + stroked; marquee inactive so fillRects = 8.
    expect(m.inner.fillRect).toHaveBeenCalledTimes(8)
  })

  it('strokes bounds for every selected element but no handles when >1 is selected', () => {
    const { store } = freshStore()
    const a = store.create({ type: 'rect', x: 0, y: 0, width: 50, height: 50 })
    const b = store.create({
      type: 'rect',
      x: 100,
      y: 0,
      width: 50,
      height: 50,
    })
    const selection = new SelectionState()
    selection.set([a, b])
    const paint = makeSelectionOverlay({
      store,
      selection,
      getMarquee: () => null,
      getViewport: () => makeViewport(),
    })
    const m = mockCtx()
    paint(m.ctx)
    expect(m.inner.strokeRect).toHaveBeenCalledTimes(2)
    expect(m.inner.fillRect).not.toHaveBeenCalled()
  })

  it('uses a solid grey outline (not dashed blue) for locked elements', () => {
    const { store } = freshStore()
    const id = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 50,
      height: 50,
      locked: true,
    })
    const selection = new SelectionState()
    selection.set([id])
    const paint = makeSelectionOverlay({
      store,
      selection,
      getMarquee: () => null,
      getViewport: () => makeViewport(),
    })
    const m = mockCtx()
    paint(m.ctx)
    // Locked elements render with a grey stroke; the dashed blue is
    // reserved for the editable selection.
    expect(m.strokeStyleLog).toContain('#64748b')
    // At least one setLineDash call passes an empty array (solid line).
    expect(m.lineDashLog.some((p) => p.length === 0)).toBe(true)
  })

  it('paints a lock badge (arc + fill) on locked elements', () => {
    const { store } = freshStore()
    const id = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 50,
      height: 50,
      locked: true,
    })
    const selection = new SelectionState()
    selection.set([id])
    const paint = makeSelectionOverlay({
      store,
      selection,
      getMarquee: () => null,
      getViewport: () => makeViewport(),
    })
    const m = mockCtx()
    paint(m.ctx)
    // Lock badge: rounded background (beginPath + fill), body (fillRect),
    // and shackle arc (arc + stroke).
    expect(m.inner.arc).toHaveBeenCalledTimes(1)
    expect(m.inner.fill).toHaveBeenCalled()
  })

  it('honours an overridden handle screen size for touch', () => {
    const { store } = freshStore()
    const id = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 100,
      height: 100,
    })
    const selection = new SelectionState()
    selection.set([id])
    const paint = makeSelectionOverlay({
      store,
      selection,
      getMarquee: () => null,
      getViewport: () => makeViewport(),
      getHandleSizePx: () => 32, // touch preset
    })
    const m = mockCtx()
    paint(m.ctx)
    // 8 handle strokeRects + 1 bounds strokeRect.
    expect(m.inner.strokeRect).toHaveBeenCalledTimes(9)
    // Each handle strokeRect is called with a 32-world-unit box at scale=1.
    const handleCalls = m.inner.strokeRect.mock.calls.slice(1)
    for (const [, , w, h] of handleCalls) {
      expect(w).toBe(32)
      expect(h).toBe(32)
    }
  })

  it('skips ids that have been deleted from the store', () => {
    const { store } = freshStore()
    const id = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 50,
      height: 50,
    })
    const selection = new SelectionState()
    selection.set([id, 'ghost-id'])
    const paint = makeSelectionOverlay({
      store,
      selection,
      getMarquee: () => null,
      getViewport: () => makeViewport(),
    })
    const m = mockCtx()
    paint(m.ctx)
    // Only the real element strokes — but it has handles too since size
    // is 2 but only 1 resolves. Wait: `selection.size === 1` checks the
    // raw set size including the ghost, so handles are NOT drawn.
    // That matches the current invariant: a stale id stays in the set
    // until SelectionState.reconcile runs.
    expect(m.inner.strokeRect).toHaveBeenCalledTimes(1) // bounds only, no handles
  })
})
