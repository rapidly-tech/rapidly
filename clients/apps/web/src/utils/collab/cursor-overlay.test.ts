import { describe, expect, it, vi } from 'vitest'

import { makeCursorOverlay } from './cursor-overlay'
import { inMemoryPresenceSource } from './presence'
import { makeViewport } from './viewport'

/** Minimal CanvasRenderingContext2D mock — we record the methods that
 *  the overlay actually calls so we can assert "did it paint that
 *  cursor or skip it?" without a real canvas. */
function mockCtx() {
  return {
    save: vi.fn(),
    restore: vi.fn(),
    translate: vi.fn(),
    scale: vi.fn(),
    beginPath: vi.fn(),
    closePath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    quadraticCurveTo: vi.fn(),
    fill: vi.fn(),
    stroke: vi.fn(),
    fillText: vi.fn(),
    measureText: vi.fn(() => ({ width: 20 })),
    fillStyle: '',
    strokeStyle: '',
    lineWidth: 0,
    lineJoin: '',
    font: '',
    textBaseline: '',
  } as unknown as CanvasRenderingContext2D & {
    fill: ReturnType<typeof vi.fn>
    translate: ReturnType<typeof vi.fn>
    fillText: ReturnType<typeof vi.fn>
  }
}

describe('makeCursorOverlay', () => {
  it('is a no-op when no remotes are present', () => {
    const source = inMemoryPresenceSource()
    const paint = makeCursorOverlay({
      source,
      getViewport: () => makeViewport(),
    })
    const ctx = mockCtx()
    paint(ctx)
    // Without remotes we return early, so translate is never called.
    expect(
      (ctx as unknown as { translate: ReturnType<typeof vi.fn> }).translate,
    ).not.toHaveBeenCalled()
  })

  it('translates to each remote cursor and fills the pointer', () => {
    const source = inMemoryPresenceSource()
    source.pushRemote({
      clientId: 1,
      user: { id: 'u1', color: '#e03131' },
      cursor: { x: 100, y: 200 },
    })
    source.pushRemote({
      clientId: 2,
      user: { id: 'u2', color: '#2f9e44' },
      cursor: { x: 10, y: 20 },
    })
    const paint = makeCursorOverlay({
      source,
      getViewport: () => makeViewport(),
    })
    const ctx = mockCtx()
    paint(ctx)
    // One translate per cursor (inside the per-cursor save).
    const tr = (ctx as unknown as { translate: ReturnType<typeof vi.fn> })
      .translate
    expect(tr).toHaveBeenCalledWith(100, 200)
    expect(tr).toHaveBeenCalledWith(10, 20)
    // Each pointer triangle ends in fill + stroke.
    const fills = (ctx as unknown as { fill: ReturnType<typeof vi.fn> }).fill
    expect(fills).toHaveBeenCalled()
  })

  it('skips peers that have no cursor published', () => {
    const source = inMemoryPresenceSource()
    source.pushRemote({
      clientId: 1,
      user: { id: 'u1', color: '#e03131' },
      // No cursor — peer is connected but their pointer left the canvas.
    })
    const paint = makeCursorOverlay({
      source,
      getViewport: () => makeViewport(),
    })
    const ctx = mockCtx()
    paint(ctx)
    expect(
      (ctx as unknown as { translate: ReturnType<typeof vi.fn> }).translate,
    ).not.toHaveBeenCalled()
  })

  it('paints the name label when showLabels is true and a name is set', () => {
    const source = inMemoryPresenceSource()
    source.pushRemote({
      clientId: 1,
      user: { id: 'u1', color: '#e03131', name: 'Alice' },
      cursor: { x: 0, y: 0 },
    })
    const paint = makeCursorOverlay({
      source,
      getViewport: () => makeViewport(),
      showLabels: true,
    })
    const ctx = mockCtx()
    paint(ctx)
    const ft = (ctx as unknown as { fillText: ReturnType<typeof vi.fn> })
      .fillText
    expect(ft).toHaveBeenCalled()
    expect(ft.mock.calls[0][0]).toBe('Alice')
  })

  it('skips the name label when showLabels is false', () => {
    const source = inMemoryPresenceSource()
    source.pushRemote({
      clientId: 1,
      user: { id: 'u1', color: '#e03131', name: 'Alice' },
      cursor: { x: 0, y: 0 },
    })
    const paint = makeCursorOverlay({
      source,
      getViewport: () => makeViewport(),
      showLabels: false,
    })
    const ctx = mockCtx()
    paint(ctx)
    expect(
      (ctx as unknown as { fillText: ReturnType<typeof vi.fn> }).fillText,
    ).not.toHaveBeenCalled()
  })
})
