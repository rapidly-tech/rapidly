import { describe, expect, it, vi } from 'vitest'

import { hueFor, isStroke, paintStroke, repaint, type Stroke } from './strokes'

describe('hueFor', () => {
  it('returns a value in [0, 360)', () => {
    for (const id of [0, 1, 42, 1_000_000]) {
      const h = hueFor(id)
      expect(h).toBeGreaterThanOrEqual(0)
      expect(h).toBeLessThan(360)
    }
  })

  it('is deterministic per clientID', () => {
    expect(hueFor(999)).toBe(hueFor(999))
  })
})

describe('isStroke', () => {
  it('accepts a valid stroke', () => {
    expect(isStroke({ by: 'a', pts: [0, 0, 1, 1], hue: 120, w: 2 })).toBe(true)
  })

  it('rejects malformed entries', () => {
    expect(isStroke(null)).toBe(false)
    expect(isStroke({ by: 1, pts: [], hue: 0, w: 1 })).toBe(false)
    expect(isStroke({ by: 'a', pts: 'nope', hue: 0, w: 1 })).toBe(false)
    expect(isStroke({ by: 'a', pts: [0, 'x'], hue: 0, w: 1 })).toBe(false)
  })
})

// A minimal CanvasRenderingContext2D stub — records the call order so we
// can assert on rendering order, then no-ops everything else.
function makeCtxStub(): CanvasRenderingContext2D & { calls: string[] } {
  const calls: string[] = []
  const ctx = {
    calls,
    lineWidth: 0,
    lineCap: '' as CanvasLineCap,
    lineJoin: '' as CanvasLineJoin,
    strokeStyle: '' as string | CanvasGradient | CanvasPattern,
    beginPath: vi.fn(() => {
      calls.push('beginPath')
    }),
    moveTo: vi.fn((x: number, y: number) => {
      calls.push(`moveTo(${x},${y})`)
    }),
    lineTo: vi.fn((x: number, y: number) => {
      calls.push(`lineTo(${x},${y})`)
    }),
    stroke: vi.fn(() => {
      calls.push('stroke')
    }),
    clearRect: vi.fn((x: number, y: number, w: number, h: number) => {
      calls.push(`clearRect(${x},${y},${w},${h})`)
    }),
  } as unknown as CanvasRenderingContext2D & { calls: string[] }
  return ctx
}

describe('paintStroke', () => {
  it('renders a single-dot stroke as a zero-length segment', () => {
    const ctx = makeCtxStub()
    paintStroke(ctx, { by: 'a', pts: [10, 20], hue: 0, w: 2 })
    expect(ctx.calls).toEqual([
      'beginPath',
      'moveTo(10,20)',
      'lineTo(10,20)',
      'stroke',
    ])
  })

  it('renders a multi-point stroke', () => {
    const ctx = makeCtxStub()
    paintStroke(ctx, { by: 'a', pts: [0, 0, 1, 1, 2, 2], hue: 0, w: 2 })
    expect(ctx.calls).toEqual([
      'beginPath',
      'moveTo(0,0)',
      'lineTo(1,1)',
      'lineTo(2,2)',
      'stroke',
    ])
  })

  it('no-ops on empty or single-coordinate pts', () => {
    const ctx = makeCtxStub()
    paintStroke(ctx, { by: 'a', pts: [], hue: 0, w: 2 })
    paintStroke(ctx, { by: 'a', pts: [5], hue: 0, w: 2 })
    expect(ctx.calls).toEqual([])
  })
})

describe('repaint', () => {
  it('clears the canvas then paints committed strokes in order', () => {
    const ctx = makeCtxStub()
    const s1: Stroke = { by: 'a', pts: [0, 0, 1, 1], hue: 0, w: 2 }
    const s2: Stroke = { by: 'b', pts: [2, 2, 3, 3], hue: 120, w: 2 }
    repaint(ctx, 100, 100, [s1, s2], null)
    expect(ctx.calls[0]).toBe('clearRect(0,0,100,100)')
    // The two strokes produce 4 calls each — verify both stroke-completes fired.
    expect(ctx.calls.filter((c) => c === 'stroke')).toHaveLength(2)
  })

  it('paints the in-progress stroke after committed strokes', () => {
    const ctx = makeCtxStub()
    const committed: Stroke = { by: 'a', pts: [0, 0, 1, 1], hue: 0, w: 2 }
    const live: Stroke = { by: 'a', pts: [5, 5, 6, 6], hue: 0, w: 2 }
    repaint(ctx, 10, 10, [committed], live)
    // Last stroke in the call list should be the live one (moveTo(5,5)).
    const moves = ctx.calls.filter((c) => c.startsWith('moveTo'))
    expect(moves).toEqual(['moveTo(0,0)', 'moveTo(5,5)'])
  })
})
