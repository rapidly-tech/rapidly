import { describe, expect, it, vi } from 'vitest'
import * as Y from 'yjs'

import { createElementStore } from './element-store'
import { inMemoryPresenceSource } from './presence'
import { makeRemoteSelectionOverlay } from './remote-selection-overlay'
import { makeViewport } from './viewport'

function mockCtx() {
  return {
    save: vi.fn(),
    restore: vi.fn(),
    translate: vi.fn(),
    rotate: vi.fn(),
    fillRect: vi.fn(),
    strokeRect: vi.fn(),
    fillStyle: '',
    strokeStyle: '',
    lineWidth: 0,
  } as unknown as CanvasRenderingContext2D & {
    fillRect: ReturnType<typeof vi.fn>
    strokeRect: ReturnType<typeof vi.fn>
    translate: ReturnType<typeof vi.fn>
  }
}

function rectOf(
  store: ReturnType<typeof createElementStore>,
  x = 0,
  y = 0,
  w = 10,
  h = 10,
): string {
  return store.create({
    type: 'rect',
    x,
    y,
    width: w,
    height: h,
    roundness: 0,
  })
}

describe('makeRemoteSelectionOverlay', () => {
  it('is a no-op when no remotes are present', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const source = inMemoryPresenceSource()
    const paint = makeRemoteSelectionOverlay({
      store,
      source,
      getViewport: () => makeViewport(),
    })
    const ctx = mockCtx()
    paint(ctx)
    expect(
      (ctx as unknown as { strokeRect: ReturnType<typeof vi.fn> }).strokeRect,
    ).not.toHaveBeenCalled()
  })

  it('skips remotes with empty or absent selections', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    rectOf(store)
    const source = inMemoryPresenceSource()
    source.pushRemote({
      clientId: 1,
      user: { id: 'u1', color: '#e03131' },
      // no selection
    })
    source.pushRemote({
      clientId: 2,
      user: { id: 'u2', color: '#2f9e44' },
      selection: [],
    })
    const paint = makeRemoteSelectionOverlay({
      store,
      source,
      getViewport: () => makeViewport(),
    })
    const ctx = mockCtx()
    paint(ctx)
    expect(
      (ctx as unknown as { strokeRect: ReturnType<typeof vi.fn> }).strokeRect,
    ).not.toHaveBeenCalled()
  })

  it('paints one fill + stroke rect per selected element', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rectOf(store)
    const b = rectOf(store)
    const source = inMemoryPresenceSource()
    source.pushRemote({
      clientId: 1,
      user: { id: 'u1', color: '#e03131' },
      selection: [a, b],
    })
    const paint = makeRemoteSelectionOverlay({
      store,
      source,
      getViewport: () => makeViewport(),
    })
    const ctx = mockCtx()
    paint(ctx)
    expect(
      (ctx as unknown as { fillRect: ReturnType<typeof vi.fn> }).fillRect,
    ).toHaveBeenCalledTimes(2)
    expect(
      (ctx as unknown as { strokeRect: ReturnType<typeof vi.fn> }).strokeRect,
    ).toHaveBeenCalledTimes(2)
  })

  it('skips selection ids not in the store', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rectOf(store)
    const source = inMemoryPresenceSource()
    source.pushRemote({
      clientId: 1,
      user: { id: 'u1', color: '#e03131' },
      selection: [a, 'ghost-id'],
    })
    const paint = makeRemoteSelectionOverlay({
      store,
      source,
      getViewport: () => makeViewport(),
    })
    const ctx = mockCtx()
    paint(ctx)
    expect(
      (ctx as unknown as { strokeRect: ReturnType<typeof vi.fn> }).strokeRect,
    ).toHaveBeenCalledTimes(1)
  })

  it('translates to the element origin before painting so rotation works', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rectOf(store, 150, 200)
    const source = inMemoryPresenceSource()
    source.pushRemote({
      clientId: 1,
      user: { id: 'u1', color: '#e03131' },
      selection: [a],
    })
    const paint = makeRemoteSelectionOverlay({
      store,
      source,
      getViewport: () => makeViewport(),
    })
    const ctx = mockCtx()
    paint(ctx)
    const tr = (ctx as unknown as { translate: ReturnType<typeof vi.fn> })
      .translate
    expect(tr).toHaveBeenCalledWith(150, 200)
  })

  it('paints every peer that has a non-empty selection', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rectOf(store)
    const source = inMemoryPresenceSource()
    source.pushRemote({
      clientId: 1,
      user: { id: 'u1', color: '#e03131' },
      selection: [a],
    })
    source.pushRemote({
      clientId: 2,
      user: { id: 'u2', color: '#2f9e44' },
      selection: [a],
    })
    const paint = makeRemoteSelectionOverlay({
      store,
      source,
      getViewport: () => makeViewport(),
    })
    const ctx = mockCtx()
    paint(ctx)
    // Same element painted once per peer.
    expect(
      (ctx as unknown as { strokeRect: ReturnType<typeof vi.fn> }).strokeRect,
    ).toHaveBeenCalledTimes(2)
  })
})
