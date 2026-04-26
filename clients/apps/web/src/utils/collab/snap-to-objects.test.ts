/**
 * Snap-to-objects — pinned behaviour:
 *
 * - Edge-to-edge alignment within the threshold snaps the delta.
 * - Centre-to-centre alignment within the threshold snaps too.
 * - Threshold is **screen px**, divided by scale → world units.
 * - X and Y snaps are independent (one axis can snap, other free).
 * - Guides span both participants on the perpendicular axis.
 * - No-op when no static bboxes are passed.
 * - No-op when no candidate is within the threshold.
 */

import { describe, expect, it } from 'vitest'

import {
  DEFAULT_SNAP_THRESHOLD_PX,
  snapToObjects,
  unionBbox,
} from './snap-to-objects'

describe('snapToObjects', () => {
  const dragged = { x: 0, y: 0, width: 50, height: 50 }

  it('snaps the left edge to a static element s left edge', () => {
    // Static element s left at x=100. If we drag to dx=99, our left
    // is at 99 — within 5 world-units (scale 1) of 100 → snap to 100.
    const result = snapToObjects({
      draggedBbox: dragged,
      dx: 99,
      dy: 0,
      staticBboxes: [{ x: 100, y: 200, width: 30, height: 30 }],
      scale: 1,
    })
    expect(result.dx).toBe(100)
    expect(result.guides[0]?.axis).toBe('x')
    expect(result.guides[0]?.world).toBe(100)
  })

  it('snaps the centre-x to a static element centre-x', () => {
    // Dragged 50×50 → centre after dx=199 sits at 224. Static 30×30
    // at x=210 → centre 225, edges 210 + 240 (both > 5 world units
    // from any dragged edge). Only centre-x is within threshold →
    // delta 1 → dx=200, guide at 225.
    const result = snapToObjects({
      draggedBbox: dragged,
      dx: 199,
      dy: 0,
      staticBboxes: [{ x: 210, y: 0, width: 30, height: 30 }],
      scale: 1,
    })
    expect(result.dx).toBe(200)
    expect(result.guides[0]?.world).toBe(225)
  })

  it('snaps the right edge to a static right edge', () => {
    // Dragged width=50; right after delta = dx + 50. Static right =
    // x + width. Static at x=300, w=20 → right=320. Pick dx=271 →
    // dragged-right=321, distance 1 → snap.
    const result = snapToObjects({
      draggedBbox: dragged,
      dx: 271,
      dy: 0,
      staticBboxes: [{ x: 300, y: 0, width: 20, height: 50 }],
      scale: 1,
    })
    expect(result.dx).toBe(270)
    expect(result.guides[0]?.world).toBe(320)
  })

  it('respects the screen-pixel threshold across zoom levels', () => {
    // At scale 0.5, 5 screen-px = 10 world-units. Use a width-matched
    // static so all three slot pairings collapse to the same delta —
    // sidesteps slot-priority ambiguity.
    // Move static y far away so the y-axis can't accidentally snap.
    const within = snapToObjects({
      draggedBbox: dragged,
      dx: 91,
      dy: 0,
      staticBboxes: [{ x: 100, y: 1000, width: 50, height: 30 }],
      scale: 0.5,
    })
    expect(within.dx).toBe(100)

    const outside = snapToObjects({
      draggedBbox: dragged,
      dx: 89,
      dy: 0,
      staticBboxes: [{ x: 100, y: 1000, width: 50, height: 30 }],
      scale: 0.5,
    })
    expect(outside.dx).toBe(89) // gap 11 > threshold 10 → no snap
    expect(outside.guides).toHaveLength(0)
  })

  it('snaps x and y independently in one call', () => {
    const result = snapToObjects({
      draggedBbox: dragged,
      dx: 99,
      dy: 199,
      staticBboxes: [{ x: 100, y: 200, width: 30, height: 30 }],
      scale: 1,
    })
    expect(result.dx).toBe(100)
    expect(result.dy).toBe(200)
    expect(result.guides).toHaveLength(2)
  })

  it('snaps the closer of two candidates on the same axis', () => {
    // Two candidates: x=100 (distance 1 from dx=99 left) and x=200
    // (distance 101). Closer wins.
    const result = snapToObjects({
      draggedBbox: dragged,
      dx: 99,
      dy: 0,
      staticBboxes: [
        { x: 100, y: 0, width: 30, height: 30 },
        { x: 200, y: 0, width: 30, height: 30 },
      ],
      scale: 1,
    })
    expect(result.dx).toBe(100)
  })

  it('is a no-op with an empty static set', () => {
    const result = snapToObjects({
      draggedBbox: dragged,
      dx: 12,
      dy: 7,
      staticBboxes: [],
      scale: 1,
    })
    expect(result).toEqual({ dx: 12, dy: 7, guides: [] })
  })

  it('is a no-op when no candidate is within the threshold', () => {
    const result = snapToObjects({
      draggedBbox: dragged,
      dx: 50,
      dy: 0,
      staticBboxes: [{ x: 200, y: 200, width: 30, height: 30 }],
      scale: 1,
    })
    expect(result.dx).toBe(50)
    expect(result.guides).toHaveLength(0)
  })

  it('builds a guide spanning both participants on the perpendicular axis', () => {
    // Dragged at (0,0) 50×50 → after dx=99 lives at (99,0)–(149,50).
    // Static at (100, 200) 30×30 → (100,200)–(130,230).
    // Guide on x at world=100 → start = min(0, 200) = 0, end = max(50, 230) = 230.
    const result = snapToObjects({
      draggedBbox: dragged,
      dx: 99,
      dy: 0,
      staticBboxes: [{ x: 100, y: 200, width: 30, height: 30 }],
      scale: 1,
    })
    expect(result.guides[0]?.start).toBe(0)
    expect(result.guides[0]?.end).toBe(230)
  })

  it('uses the configured threshold when provided', () => {
    // 1-px threshold: 9 world-units gap at scale 1 → no snap on any
    // slot. Width-matched static so no other slot accidentally falls
    // inside the tighter threshold.
    const result = snapToObjects({
      draggedBbox: dragged,
      dx: 91,
      dy: 0,
      staticBboxes: [{ x: 100, y: 0, width: 50, height: 30 }],
      scale: 1,
      thresholdPx: 1,
    })
    expect(result.dx).toBe(91)
  })

  it('exports a sensible default threshold', () => {
    expect(DEFAULT_SNAP_THRESHOLD_PX).toBeGreaterThanOrEqual(3)
    expect(DEFAULT_SNAP_THRESHOLD_PX).toBeLessThanOrEqual(10)
  })
})

describe('unionBbox', () => {
  it('returns null on empty input', () => {
    expect(unionBbox([])).toBeNull()
  })

  it('matches a single element exactly', () => {
    expect(unionBbox([{ x: 5, y: 5, width: 10, height: 10 }])).toEqual({
      x: 5,
      y: 5,
      width: 10,
      height: 10,
    })
  })

  it('covers many elements', () => {
    expect(
      unionBbox([
        { x: 0, y: 0, width: 10, height: 10 },
        { x: 100, y: 50, width: 30, height: 30 },
      ]),
    ).toEqual({ x: 0, y: 0, width: 130, height: 80 })
  })
})
