import { beforeAll, describe, expect, it, vi } from 'vitest'
import * as Y from 'yjs'

// jsdom ships no Path2D; shape adapters construct one per element.
// Stub the constructor so ``paintElementsOnto`` can run.
beforeAll(() => {
  if (typeof (globalThis as { Path2D?: unknown }).Path2D === 'undefined') {
    ;(globalThis as { Path2D: unknown }).Path2D = class {
      rect() {}
      ellipse() {}
      moveTo() {}
      lineTo() {}
      quadraticCurveTo() {}
      bezierCurveTo() {}
      arc() {}
      closePath() {}
    }
  }
})

import { createElementStore } from './element-store'
import {
  computeBounds,
  EXPORT_SCHEMA,
  exportToJSON,
  exportToPNG,
  paintElementsOnto,
} from './export'

function rect(
  store: ReturnType<typeof createElementStore>,
  overrides: Record<string, unknown> = {},
): string {
  return store.create({
    type: 'rect',
    x: 0,
    y: 0,
    width: 10,
    height: 10,
    roundness: 0,
    ...overrides,
  })
}

describe('computeBounds', () => {
  it('returns null on an empty element list', () => {
    expect(computeBounds([])).toBeNull()
  })

  it('covers every element in world coords', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    rect(store, { x: 0, y: 0, width: 10, height: 10 })
    rect(store, { x: 50, y: 20, width: 30, height: 40 })
    const bounds = computeBounds(store.list())!
    expect(bounds.x).toBe(0)
    expect(bounds.y).toBe(0)
    expect(bounds.width).toBe(80)
    expect(bounds.height).toBe(60)
  })

  it('handles negative coordinates', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    rect(store, { x: -50, y: -30, width: 10, height: 10 })
    rect(store, { x: 20, y: 0, width: 10, height: 10 })
    const bounds = computeBounds(store.list())!
    expect(bounds.x).toBe(-50)
    expect(bounds.y).toBe(-30)
    expect(bounds.width).toBe(80)
    expect(bounds.height).toBe(40)
  })
})

describe('exportToJSON', () => {
  it('wraps elements in a versioned envelope', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    rect(store)
    const payload = exportToJSON(store.list())
    expect(payload.schema).toBe(EXPORT_SCHEMA)
    expect(payload.version).toBe(1)
    expect(payload.elements).toHaveLength(1)
  })

  it('clones elements by value — later edits do not leak', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = rect(store, { x: 100 })
    const payload = exportToJSON(store.list())
    store.update(id, { x: 500 })
    expect(payload.elements[0].x).toBe(100)
  })

  it('JSON-stringifies round-trip to the same shape', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    rect(store)
    const payload = exportToJSON(store.list())
    const round = JSON.parse(JSON.stringify(payload))
    expect(round.schema).toBe(EXPORT_SCHEMA)
    expect(round.elements[0].type).toBe('rect')
  })
})

describe('paintElementsOnto', () => {
  function mockCtx() {
    return {
      save: vi.fn(),
      restore: vi.fn(),
      translate: vi.fn(),
      rotate: vi.fn(),
      scale: vi.fn(),
      beginPath: vi.fn(),
      closePath: vi.fn(),
      moveTo: vi.fn(),
      lineTo: vi.fn(),
      quadraticCurveTo: vi.fn(),
      stroke: vi.fn(),
      fill: vi.fn(),
      strokeRect: vi.fn(),
      fillRect: vi.fn(),
      setLineDash: vi.fn(),
      arc: vi.fn(),
      ellipse: vi.fn(),
      drawImage: vi.fn(),
      fillStyle: '',
      strokeStyle: '',
      lineWidth: 0,
      globalAlpha: 1,
      lineJoin: '',
    } as unknown as CanvasRenderingContext2D
  }

  it('applies offset + scale before iterating elements', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    rect(store, { x: 50, y: 50 })
    const ctx = mockCtx()
    paintElementsOnto(ctx, store.list(), {
      offsetX: 10,
      offsetY: 20,
      scale: 2,
    })
    const tr = (ctx as unknown as { translate: ReturnType<typeof vi.fn> })
      .translate
    const sc = (ctx as unknown as { scale: ReturnType<typeof vi.fn> }).scale
    // Scale applied once at the top of the pass.
    expect(sc).toHaveBeenCalledWith(2, 2)
    // Negative offset translate applied right after scale.
    expect(tr).toHaveBeenCalledWith(-10, -20)
  })

  it('translates to each element origin', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    rect(store, { x: 100, y: 200 })
    rect(store, { x: 300, y: 400 })
    const ctx = mockCtx()
    paintElementsOnto(ctx, store.list(), {
      offsetX: 0,
      offsetY: 0,
      scale: 1,
    })
    const tr = (ctx as unknown as { translate: ReturnType<typeof vi.fn> })
      .translate
    expect(tr).toHaveBeenCalledWith(100, 200)
    expect(tr).toHaveBeenCalledWith(300, 400)
  })

  it('skips elements without a registered shape adapter', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    rect(store)
    // Cast-through-unknown to inject a fake type the registry skips.
    // Every concrete element type is now wired, so we use a forward-
    // compat sentinel — the kind a peer running a newer build might
    // emit before we know about it.
    const list = [
      ...store.list(),
      {
        ...store.list()[0],
        id: 'ghost',
        type: 'future-element-kind' as const,
      },
    ] as unknown as Parameters<typeof paintElementsOnto>[1]
    const ctx = mockCtx()
    // Should not throw even when the registry doesn't know the type.
    expect(() =>
      paintElementsOnto(ctx, list, { offsetX: 0, offsetY: 0, scale: 1 }),
    ).not.toThrow()
  })
})

describe('exportToPNG', () => {
  it('resolves null for an empty scene', async () => {
    const blob = await exportToPNG([])
    expect(blob).toBeNull()
  })

  it('uses the injected canvas factory', async () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    rect(store, { x: 0, y: 0, width: 100, height: 100 })
    const fakeCanvas = {
      width: 0,
      height: 0,
      getContext: vi.fn(() => null),
      toBlob: vi.fn((cb: BlobCallback) => cb(null)),
    } as unknown as HTMLCanvasElement
    const createCanvas = vi.fn(() => fakeCanvas)
    await exportToPNG(store.list(), { createCanvas })
    expect(createCanvas).toHaveBeenCalledTimes(1)
    expect(fakeCanvas.width).toBeGreaterThan(0)
    expect(fakeCanvas.height).toBeGreaterThan(0)
  })

  it('returns null when the canvas has no 2d context', async () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    rect(store)
    const fakeCanvas = {
      width: 0,
      height: 0,
      getContext: () => null,
    } as unknown as HTMLCanvasElement
    const out = await exportToPNG(store.list(), {
      createCanvas: () => fakeCanvas,
    })
    expect(out).toBeNull()
  })
})
