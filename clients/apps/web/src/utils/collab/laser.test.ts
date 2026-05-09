import { describe, expect, it, vi } from 'vitest'

import { ageToAlpha, createLaserState } from './laser'
import { makeLaserOverlay } from './laser-overlay'
import { inMemoryPresenceSource } from './presence'
import { makeViewport } from './viewport'

describe('createLaserState', () => {
  it('push records a point and returns the updated snapshot', () => {
    const laser = createLaserState({ ttlMs: 1000 })
    const snap = laser.push(10, 20, 100)
    expect(snap.points).toHaveLength(1)
    expect(snap.points[0]).toEqual({ x: 10, y: 20, t: 100 })
  })

  it('prunes points older than the TTL', () => {
    const laser = createLaserState({ ttlMs: 500 })
    laser.push(0, 0, 0)
    laser.push(1, 1, 200)
    const snap = laser.push(2, 2, 600) // 0 is now 600ms old, prune it
    expect(snap.points.map((p) => p.t)).toEqual([200, 600])
  })

  it('snapshot prunes to the supplied now', () => {
    const laser = createLaserState({ ttlMs: 500 })
    laser.push(0, 0, 0)
    laser.push(1, 1, 100)
    laser.push(2, 2, 200)
    const snap = laser.snapshot(700)
    expect(snap.points.map((p) => p.t)).toEqual([200])
  })

  it('caps the trail to maxPoints oldest-first', () => {
    const laser = createLaserState({ ttlMs: 10_000, maxPoints: 3 })
    for (let i = 0; i < 10; i++) laser.push(i, i, i)
    const snap = laser.snapshot(9)
    expect(snap.points).toHaveLength(3)
    // Newest three — i = 7, 8, 9.
    expect(snap.points.map((p) => p.x)).toEqual([7, 8, 9])
  })

  it('clear drops every sample', () => {
    const laser = createLaserState()
    laser.push(0, 0, 0)
    laser.clear()
    expect(laser.snapshot(0).points).toEqual([])
  })

  it('snapshot returns a new array (safe to hand to React render)', () => {
    const laser = createLaserState()
    laser.push(0, 0, 0)
    const a = laser.snapshot(0)
    const b = laser.snapshot(0)
    expect(a.points).not.toBe(b.points)
  })
})

describe('ageToAlpha', () => {
  it('returns 1 at age 0 and 0 past TTL', () => {
    expect(ageToAlpha(0, 1000)).toBe(1)
    expect(ageToAlpha(1000, 1000)).toBe(0)
    expect(ageToAlpha(9999, 1000)).toBe(0)
  })

  it('is monotonically decreasing', () => {
    let prev = 1
    for (const age of [0, 100, 200, 400, 800, 1000]) {
      const v = ageToAlpha(age, 1000)
      expect(v).toBeLessThanOrEqual(prev)
      prev = v
    }
  })

  it('ease-out: still bright early, fades hard near end', () => {
    // At half the TTL, alpha should still be clearly > 0.5 because of
    // the ease-out curve (1 - t^2 at t=0.5 = 0.75).
    expect(ageToAlpha(500, 1000)).toBeGreaterThan(0.5)
  })
})

describe('makeLaserOverlay', () => {
  function mockCtx() {
    return {
      save: vi.fn(),
      restore: vi.fn(),
      beginPath: vi.fn(),
      moveTo: vi.fn(),
      lineTo: vi.fn(),
      stroke: vi.fn(),
      arc: vi.fn(),
      fill: vi.fn(),
      strokeStyle: '',
      fillStyle: '',
      lineWidth: 0,
      lineCap: '',
      lineJoin: '',
      globalAlpha: 1,
    } as unknown as CanvasRenderingContext2D
  }

  it('no-op when no remotes', () => {
    const paint = makeLaserOverlay({
      source: inMemoryPresenceSource(),
      getViewport: () => makeViewport(),
    })
    const ctx = mockCtx()
    paint(ctx)
    const mocked = ctx as unknown as { stroke: ReturnType<typeof vi.fn> }
    expect(mocked.stroke).not.toHaveBeenCalled()
  })

  it('paints one stroke per connecting segment + one head dot', () => {
    const source = inMemoryPresenceSource()
    source.pushRemote({
      clientId: 1,
      user: { id: 'u1', color: '#e03131' },
      laser: {
        points: [
          { x: 0, y: 0, t: 0 },
          { x: 10, y: 0, t: 100 },
          { x: 20, y: 0, t: 200 },
        ],
      },
    })
    const paint = makeLaserOverlay({
      source,
      getViewport: () => makeViewport(),
    })
    const ctx = mockCtx()
    paint(ctx)
    // Two segments (3 points → 2 connecting lines).
    const stroke = (ctx as unknown as { stroke: ReturnType<typeof vi.fn> })
      .stroke
    expect(stroke).toHaveBeenCalledTimes(2)
    // Head dot via arc + fill.
    const arc = (ctx as unknown as { arc: ReturnType<typeof vi.fn> }).arc
    expect(arc).toHaveBeenCalledTimes(1)
  })

  it('skips a peer with no laser data', () => {
    const source = inMemoryPresenceSource()
    source.pushRemote({
      clientId: 1,
      user: { id: 'u1', color: '#e03131' },
      // no laser field
    })
    const paint = makeLaserOverlay({
      source,
      getViewport: () => makeViewport(),
    })
    const ctx = mockCtx()
    paint(ctx)
    const mocked = ctx as unknown as { stroke: ReturnType<typeof vi.fn> }
    expect(mocked.stroke).not.toHaveBeenCalled()
  })
})
