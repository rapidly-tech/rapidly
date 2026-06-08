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
  activeSidesForHandle,
  snapPointToObjects,
  snapResizeBbox,
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

describe('snapPointToObjects', () => {
  it('snaps to a static element s left edge', () => {
    const result = snapPointToObjects(
      { x: 99, y: 1000 },
      [{ x: 100, y: 0, width: 50, height: 50 }],
      1,
    )
    expect(result.x).toBe(100)
    expect(result.y).toBe(1000) // y far away → no y snap
    expect(result.guides[0]?.axis).toBe('x')
  })

  it('snaps to a centre line when closer than the edge', () => {
    // Static at x=200, w=50 → edges 200 + 250, centre 225.
    // Point at x=224 → centre wins (1) over left edge (24).
    const result = snapPointToObjects(
      { x: 224, y: 0 },
      [{ x: 200, y: 0, width: 50, height: 50 }],
      1,
    )
    expect(result.x).toBe(225)
  })

  it('snaps x and y independently in one call', () => {
    const result = snapPointToObjects(
      { x: 99, y: 199 },
      [{ x: 100, y: 200, width: 30, height: 30 }],
      1,
    )
    expect(result.x).toBe(100)
    expect(result.y).toBe(200)
    expect(result.guides).toHaveLength(2)
  })

  it('respects the screen threshold across zoom', () => {
    // scale 0.5 ⇒ 5 screen-px = 10 world. 9-unit gap snaps; 11 doesn t.
    const within = snapPointToObjects(
      { x: 91, y: 1000 },
      [{ x: 100, y: 0, width: 50, height: 50 }],
      0.5,
    )
    expect(within.x).toBe(100)
    const outside = snapPointToObjects(
      { x: 89, y: 1000 },
      [{ x: 100, y: 0, width: 50, height: 50 }],
      0.5,
    )
    expect(outside.x).toBe(89)
    expect(outside.guides).toHaveLength(0)
  })

  it('is a no-op for an empty static set', () => {
    expect(snapPointToObjects({ x: 7, y: 11 }, [], 1)).toEqual({
      x: 7,
      y: 11,
      guides: [],
    })
  })

  it('uses a custom threshold when provided', () => {
    // 1-px threshold at scale 1: gap of 4 → no snap.
    const result = snapPointToObjects(
      { x: 96, y: 1000 },
      [{ x: 100, y: 0, width: 50, height: 50 }],
      1,
      1,
    )
    expect(result.x).toBe(96)
  })
})

describe('snapResizeBbox', () => {
  const statics = [{ x: 100, y: 0, width: 50, height: 50 }]

  it('snaps the right edge when the e handle is active', () => {
    // Bbox right = 99; pull to static left at 100 (edge match within
    // threshold). Width grows by 1.
    const result = snapResizeBbox(
      { x: 0, y: 1000, width: 99, height: 20 },
      { right: true },
      statics,
      1,
    )
    expect(result.bbox.x).toBe(0)
    expect(result.bbox.width).toBe(100)
    expect(result.guides[0]?.world).toBe(100)
  })

  it('snaps the left edge when the w handle is active', () => {
    // Bbox left at 99 → snap to 100; width shrinks by 1.
    const result = snapResizeBbox(
      { x: 99, y: 1000, width: 100, height: 20 },
      { left: true },
      statics,
      1,
    )
    expect(result.bbox.x).toBe(100)
    expect(result.bbox.width).toBe(99)
  })

  it('snaps top + left for a NW handle drag', () => {
    // Static top at y=0, left at x=100. Bbox at (99, 1) 50×50 →
    // pull both edges; check both axes.
    const result = snapResizeBbox(
      { x: 99, y: 1, width: 50, height: 50 },
      { top: true, left: true },
      statics,
      1,
    )
    expect(result.bbox.x).toBe(100)
    expect(result.bbox.y).toBe(0)
    expect(result.guides).toHaveLength(2)
  })

  it('drops a snap that would invert the bbox', () => {
    // Tiny bbox (width=2). A right-edge snap to a far left line
    // would produce negative width; helper must keep the original.
    const result = snapResizeBbox(
      { x: 200, y: 1000, width: 2, height: 20 },
      { right: true },
      [{ x: 100, y: 0, width: 1, height: 1 }],
      1,
    )
    // No snap emitted; bbox unchanged.
    expect(result.bbox).toEqual({ x: 200, y: 1000, width: 2, height: 20 })
    expect(result.guides).toHaveLength(0)
  })

  it('is a no-op with no static elements', () => {
    const bbox = { x: 0, y: 0, width: 10, height: 10 }
    expect(snapResizeBbox(bbox, { right: true }, [], 1)).toEqual({
      bbox,
      guides: [],
    })
  })

  it('respects the screen threshold across zoom', () => {
    // At scale 0.5, 5 screen-px = 10 world. A 9-unit gap on the right
    // edge snaps; an 11 doesn t.
    const within = snapResizeBbox(
      { x: 0, y: 1000, width: 91, height: 20 },
      { right: true },
      statics,
      0.5,
    )
    expect(within.bbox.width).toBe(100)
    const outside = snapResizeBbox(
      { x: 0, y: 1000, width: 89, height: 20 },
      { right: true },
      statics,
      0.5,
    )
    expect(outside.bbox.width).toBe(89)
  })
})

describe('activeSidesForHandle', () => {
  it('maps cardinal handles to a single side', () => {
    expect(activeSidesForHandle('n')).toEqual({ top: true })
    expect(activeSidesForHandle('s')).toEqual({ bottom: true })
    expect(activeSidesForHandle('e')).toEqual({ right: true })
    expect(activeSidesForHandle('w')).toEqual({ left: true })
  })

  it('maps corner handles to two sides', () => {
    expect(activeSidesForHandle('nw')).toEqual({ top: true, left: true })
    expect(activeSidesForHandle('ne')).toEqual({ top: true, right: true })
    expect(activeSidesForHandle('sw')).toEqual({ bottom: true, left: true })
    expect(activeSidesForHandle('se')).toEqual({ bottom: true, right: true })
  })

  it('returns empty for unrecognised handles', () => {
    expect(activeSidesForHandle('rotation')).toEqual({})
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
