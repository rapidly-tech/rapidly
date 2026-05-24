import { describe, expect, it, vi } from 'vitest'

import { ageToAlpha } from './laser'
import { makeLaserOverlay } from './laser-overlay'
import { inMemoryPresenceSource } from './presence'
import { makeViewport } from './viewport'

/** Canvas-context stub that records method calls + the sequence of
 *  ``globalAlpha`` assignments so tests can assert the fade curve. */
function mockCtx() {
  const alphaLog: number[] = []
  const inner = {
    save: vi.fn(),
    restore: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    stroke: vi.fn(),
    arc: vi.fn(),
    fill: vi.fn(),
    fillStyle: '',
    strokeStyle: '',
    lineWidth: 0,
    lineCap: '',
    lineJoin: '',
  }
  Object.defineProperty(inner, 'globalAlpha', {
    set(v: number) {
      alphaLog.push(v)
    },
    get() {
      return alphaLog.length > 0 ? alphaLog[alphaLog.length - 1] : 1
    },
    configurable: true,
  })
  return {
    ctx: inner as unknown as CanvasRenderingContext2D,
    inner: inner as unknown as {
      save: ReturnType<typeof vi.fn>
      restore: ReturnType<typeof vi.fn>
      beginPath: ReturnType<typeof vi.fn>
      moveTo: ReturnType<typeof vi.fn>
      lineTo: ReturnType<typeof vi.fn>
      stroke: ReturnType<typeof vi.fn>
      arc: ReturnType<typeof vi.fn>
      fill: ReturnType<typeof vi.fn>
    },
    alphaLog,
  }
}

describe('makeLaserOverlay', () => {
  it('is a no-op when the presence source has no remotes', () => {
    const source = inMemoryPresenceSource()
    const paint = makeLaserOverlay({
      source,
      getViewport: () => makeViewport(),
    })
    const m = mockCtx()
    paint(m.ctx)
    expect(m.inner.save).not.toHaveBeenCalled()
    expect(m.inner.stroke).not.toHaveBeenCalled()
    expect(m.inner.arc).not.toHaveBeenCalled()
  })

  it('skips peers that have no active laser trail', () => {
    const source = inMemoryPresenceSource()
    source.pushRemote({
      clientId: 1,
      user: { id: 'u1', color: '#e03131' },
      cursor: { x: 10, y: 20 },
      // No laser field — peer is present but not holding the laser tool.
    })
    const paint = makeLaserOverlay({
      source,
      getViewport: () => makeViewport(),
    })
    const m = mockCtx()
    paint(m.ctx)
    // The outer save/restore still runs once per paint, but the per-peer
    // inner save must not, because paintOne returns before it.
    expect(m.inner.stroke).not.toHaveBeenCalled()
    expect(m.inner.arc).not.toHaveBeenCalled()
  })

  it('strokes trail segments and fills a head dot for a live laser', () => {
    const source = inMemoryPresenceSource()
    source.pushRemote({
      clientId: 1,
      user: { id: 'u1', color: '#ef4444' },
      cursor: { x: 30, y: 40 },
      laser: {
        points: [
          { x: 0, y: 0, t: 0 },
          { x: 10, y: 10, t: 100 },
          { x: 20, y: 20, t: 200 },
          { x: 30, y: 40, t: 300 },
        ],
      },
    })
    const paint = makeLaserOverlay({
      source,
      getViewport: () => makeViewport(),
    })
    const m = mockCtx()
    paint(m.ctx)
    // 3 segments for 4 points.
    expect(m.inner.stroke).toHaveBeenCalledTimes(3)
    expect(m.inner.moveTo).toHaveBeenCalledWith(0, 0)
    expect(m.inner.moveTo).toHaveBeenCalledWith(10, 10)
    expect(m.inner.moveTo).toHaveBeenCalledWith(20, 20)
    // Head dot — arc + fill, using the latest point (30, 40).
    expect(m.inner.arc).toHaveBeenCalledTimes(1)
    expect(m.inner.arc.mock.calls[0][0]).toBe(30)
    expect(m.inner.arc.mock.calls[0][1]).toBe(40)
    expect(m.inner.fill).toHaveBeenCalled()
  })

  it('fades segments by age (newest opaque, oldest translucent)', () => {
    const source = inMemoryPresenceSource()
    source.pushRemote({
      clientId: 1,
      user: { id: 'u1', color: '#ef4444' },
      laser: {
        points: [
          { x: 0, y: 0, t: 0 }, // age 300 from newestT
          { x: 10, y: 10, t: 100 }, // age 200
          { x: 20, y: 20, t: 300 }, // newest
        ],
      },
    })
    const paint = makeLaserOverlay({
      source,
      getViewport: () => makeViewport(),
    })
    const m = mockCtx()
    paint(m.ctx)
    // N points → N-1 segments. Each segment's alpha is taken from its
    // older endpoint: ageToAlpha(newestT - points[i-1].t).
    const segAlphas = m.alphaLog.slice(0, 2)
    expect(segAlphas[0]).toBeCloseTo(ageToAlpha(300)) // point 0 at t=0
    expect(segAlphas[1]).toBeCloseTo(ageToAlpha(200)) // point 1 at t=100
    // Older segment should fade more than the newer one.
    expect(segAlphas[0]).toBeLessThan(segAlphas[1])
    // Head dot assigns globalAlpha=1 before fill.
    expect(m.alphaLog[m.alphaLog.length - 1]).toBe(1)
  })

  it('paints every peer that has a trail', () => {
    const source = inMemoryPresenceSource()
    source.pushRemote({
      clientId: 1,
      user: { id: 'u1', color: '#ef4444' },
      laser: {
        points: [
          { x: 0, y: 0, t: 0 },
          { x: 10, y: 10, t: 100 },
        ],
      },
    })
    source.pushRemote({
      clientId: 2,
      user: { id: 'u2', color: '#2f9e44' },
      laser: {
        points: [
          { x: 50, y: 50, t: 0 },
          { x: 60, y: 60, t: 100 },
        ],
      },
    })
    const paint = makeLaserOverlay({
      source,
      getViewport: () => makeViewport(),
    })
    const m = mockCtx()
    paint(m.ctx)
    // One segment + one head per peer → 2 strokes, 2 arcs.
    expect(m.inner.stroke).toHaveBeenCalledTimes(2)
    expect(m.inner.arc).toHaveBeenCalledTimes(2)
  })
})
