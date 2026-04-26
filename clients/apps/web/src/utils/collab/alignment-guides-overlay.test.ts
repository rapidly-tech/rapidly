/**
 * Alignment-guides overlay — pinned behaviour:
 *
 * - Empty guide list → no draw calls.
 * - Vertical (axis='x') guide moves to world.x then lines to (world, end).
 * - Horizontal (axis='y') guide moves to (start, world) then lines.
 * - Stroke + dash divide by scale so the line stays 1 px / 4-3 dash on
 *   screen regardless of zoom.
 */

import { describe, expect, it, vi } from 'vitest'

import { makeAlignmentGuidesOverlay } from './alignment-guides-overlay'
import type { SnapGuide } from './snap-to-objects'
import { makeViewport } from './viewport'

interface FakeCtx {
  save: ReturnType<typeof vi.fn>
  restore: ReturnType<typeof vi.fn>
  beginPath: ReturnType<typeof vi.fn>
  stroke: ReturnType<typeof vi.fn>
  moveTo: ReturnType<typeof vi.fn>
  lineTo: ReturnType<typeof vi.fn>
  setLineDash: ReturnType<typeof vi.fn>
  strokeStyle: string
  lineWidth: number
}

function fakeCtx(): FakeCtx {
  return {
    save: vi.fn(),
    restore: vi.fn(),
    beginPath: vi.fn(),
    stroke: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    setLineDash: vi.fn(),
    strokeStyle: '',
    lineWidth: 0,
  }
}

describe('makeAlignmentGuidesOverlay', () => {
  it('paints nothing when the guide list is empty', () => {
    const ctx = fakeCtx()
    const paint = makeAlignmentGuidesOverlay({
      getGuides: () => [],
      getViewport: () => makeViewport(),
    })
    paint(ctx as unknown as CanvasRenderingContext2D)
    expect(ctx.beginPath).not.toHaveBeenCalled()
    expect(ctx.save).not.toHaveBeenCalled()
  })

  it('draws a vertical line for axis=x guides', () => {
    const ctx = fakeCtx()
    const guides: SnapGuide[] = [{ axis: 'x', world: 100, start: 10, end: 200 }]
    const paint = makeAlignmentGuidesOverlay({
      getGuides: () => guides,
      getViewport: () => makeViewport({ scale: 1 }),
    })
    paint(ctx as unknown as CanvasRenderingContext2D)
    expect(ctx.moveTo).toHaveBeenCalledWith(100, 10)
    expect(ctx.lineTo).toHaveBeenCalledWith(100, 200)
    expect(ctx.stroke).toHaveBeenCalledTimes(1)
  })

  it('draws a horizontal line for axis=y guides', () => {
    const ctx = fakeCtx()
    const guides: SnapGuide[] = [{ axis: 'y', world: 50, start: 0, end: 300 }]
    const paint = makeAlignmentGuidesOverlay({
      getGuides: () => guides,
      getViewport: () => makeViewport({ scale: 1 }),
    })
    paint(ctx as unknown as CanvasRenderingContext2D)
    expect(ctx.moveTo).toHaveBeenCalledWith(0, 50)
    expect(ctx.lineTo).toHaveBeenCalledWith(300, 50)
  })

  it('paints both guides when x and y are present', () => {
    const ctx = fakeCtx()
    const guides: SnapGuide[] = [
      { axis: 'x', world: 100, start: 0, end: 50 },
      { axis: 'y', world: 200, start: 0, end: 80 },
    ]
    const paint = makeAlignmentGuidesOverlay({
      getGuides: () => guides,
      getViewport: () => makeViewport({ scale: 1 }),
    })
    paint(ctx as unknown as CanvasRenderingContext2D)
    expect(ctx.stroke).toHaveBeenCalledTimes(2)
  })

  it('scales line width by 1/scale so it stays screen-constant', () => {
    const ctx = fakeCtx()
    const guides: SnapGuide[] = [{ axis: 'x', world: 100, start: 0, end: 10 }]
    const paint = makeAlignmentGuidesOverlay({
      getGuides: () => guides,
      getViewport: () => makeViewport({ scale: 2 }),
    })
    paint(ctx as unknown as CanvasRenderingContext2D)
    expect(ctx.lineWidth).toBeCloseTo(0.5)
    // Dash should also halve (8/3 * 2 → 4/3 in world units would
    // appear 8 px on screen; we want 4-3 dash → 2/1.5 in world).
    expect(ctx.setLineDash).toHaveBeenCalledWith([2, 1.5])
  })

  it('skips painting at scale 0', () => {
    const ctx = fakeCtx()
    const guides: SnapGuide[] = [{ axis: 'x', world: 100, start: 0, end: 10 }]
    const paint = makeAlignmentGuidesOverlay({
      getGuides: () => guides,
      getViewport: () => makeViewport({ scale: 0 }),
    })
    paint(ctx as unknown as CanvasRenderingContext2D)
    expect(ctx.stroke).not.toHaveBeenCalled()
  })
})
