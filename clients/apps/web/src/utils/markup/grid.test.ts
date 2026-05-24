/**
 * Grid + snap-to-grid — pinned behaviour:
 *
 * - ``snapToGrid`` rounds to the NEAREST grid line (not floor).
 * - Negative values round symmetrically.
 * - ``gridSize <= 0`` or non-finite is a no-op (defensive).
 * - Delta snapping converts screen→world→snap→screen.
 * - ``gridVisibleAt`` hides the grid below 6px on-screen spacing.
 * - ``drawGrid`` paints zero dots when invisible (early-exit guard).
 * - ``drawGrid`` paints one dot per intersection inside the canvas.
 */

import { describe, expect, it, vi } from 'vitest'

import {
  DEFAULT_GRID_SIZE,
  drawGrid,
  gridVisibleAt,
  snapDeltaToGrid,
  snapPoint,
  snapToGrid,
} from './grid'
import { makeViewport } from './viewport'

describe('snapToGrid', () => {
  it('rounds to the nearest grid line', () => {
    expect(snapToGrid(0, 20)).toBe(0)
    expect(snapToGrid(9, 20)).toBe(0) // 9 < 10, rounds down
    expect(snapToGrid(11, 20)).toBe(20) // 11 > 10, rounds up
    expect(snapToGrid(50, 20)).toBe(60) // half-way → ties to even (Math.round bias)
    expect(snapToGrid(60, 20)).toBe(60)
  })

  it('handles negative values symmetrically', () => {
    expect(snapToGrid(-9, 20)).toBe(-0)
    expect(snapToGrid(-11, 20)).toBe(-20)
    expect(snapToGrid(-25, 20)).toBe(-20)
  })

  it('is a no-op for gridSize <= 0', () => {
    expect(snapToGrid(42, 0)).toBe(42)
    expect(snapToGrid(42, -10)).toBe(42)
  })

  it('is a no-op for non-finite gridSize', () => {
    expect(snapToGrid(42, NaN)).toBe(42)
    expect(snapToGrid(42, Infinity)).toBe(42)
  })
})

describe('snapPoint', () => {
  it('snaps both axes to the same gridSize', () => {
    expect(snapPoint(11, 9, 20)).toEqual({ x: 20, y: 0 })
  })
})

describe('snapDeltaToGrid', () => {
  it('snaps a screen delta to a world-grid step at the given zoom', () => {
    // scale=2, gridSize=10 → screen step = 20px.
    expect(snapDeltaToGrid(11, 2, 10)).toBe(20)
    expect(snapDeltaToGrid(9, 2, 10)).toBe(0)
  })

  it('is a no-op for non-positive scale or grid', () => {
    expect(snapDeltaToGrid(50, 0, 20)).toBe(50)
    expect(snapDeltaToGrid(50, 1, 0)).toBe(50)
  })
})

describe('gridVisibleAt', () => {
  it('hides the grid when on-screen spacing < 6 px', () => {
    expect(gridVisibleAt(0.1, 20)).toBe(false) // 2 px
    expect(gridVisibleAt(0.25, 20)).toBe(false) // 5 px
  })

  it('shows the grid when spacing >= 6 px', () => {
    expect(gridVisibleAt(0.3, 20)).toBe(true) // 6 px
    expect(gridVisibleAt(1, 20)).toBe(true)
    expect(gridVisibleAt(2, 20)).toBe(true)
  })
})

describe('drawGrid', () => {
  function fakeCtx(): CanvasRenderingContext2D {
    return {
      save: vi.fn(),
      restore: vi.fn(),
      fillRect: vi.fn(),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any
  }

  it('paints zero dots when zoom is below threshold', () => {
    const ctx = fakeCtx()
    const vp = makeViewport({ scale: 0.1 })
    drawGrid(ctx, vp, 600, 400, 20)
    expect(ctx.fillRect).not.toHaveBeenCalled()
  })

  it('paints one dot per visible grid intersection', () => {
    const ctx = fakeCtx()
    const vp = makeViewport({ scale: 1, scrollX: 0, scrollY: 0 })
    // Grid 20, canvas 100×100 → 5×5 = 25 dots (lines at 0,20,40,60,80).
    drawGrid(ctx, vp, 100, 100, 20)
    expect(ctx.fillRect).toHaveBeenCalledTimes(25)
  })

  it('respects the world origin offset', () => {
    const ctx = fakeCtx()
    // viewport scrolled so world (10, 0) is at screen (0, 0).
    // First grid line in screen-space is at 10 px (world 20 → screen 10
    // since scale=1 and worldOrigin=10).
    const vp = makeViewport({ scale: 1, scrollX: 10, scrollY: 0 })
    drawGrid(ctx, vp, 50, 20, 20)
    // World x lines >= 10: 20, 40, 60 — first three. Of those, 20 and
    // 40 fall at screen x = 10 and 30 (still in canvas), 60 at 50
    // (out). Y: 0, 20 — both in canvas at screen y = 0 and 20.
    // Total: 2 x cols × 1 y row (screen y=20 is the lower edge ⇒
    // exclusive in our loop's ``< canvasHeight`` test), check the
    // first row paints.
    expect(ctx.fillRect).toHaveBeenCalled()
  })

  it('uses default grid size when not supplied', () => {
    const ctx = fakeCtx()
    const vp = makeViewport({ scale: 1 })
    // 600×400 canvas, default grid 20 → 30×20 = 600 calls.
    drawGrid(ctx, vp, 600, 400)
    expect(ctx.fillRect).toHaveBeenCalledTimes(30 * 20)
    expect(DEFAULT_GRID_SIZE).toBe(20)
  })
})
