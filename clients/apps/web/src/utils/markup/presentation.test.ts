import { describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import { createElementStore } from './element-store'
import { advanceFrame, computeFrames, viewportForBounds } from './presentation'

describe('computeFrames', () => {
  it('returns an empty list on an empty scene', () => {
    expect(computeFrames([])).toEqual([])
  })

  it('one frame per element, ordered by zIndex (paint order)', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      roundness: 0,
    })
    const b = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      roundness: 0,
    })
    // b was created after a, so its zIndex is higher.
    const frames = computeFrames(store.list())
    expect(frames.map((f) => f.id)).toEqual([a, b])
  })

  it('applies padding to the bounds', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    store.create({
      type: 'rect',
      x: 100,
      y: 100,
      width: 50,
      height: 50,
      roundness: 0,
    })
    const frame = computeFrames(store.list(), { padding: 10 })[0]
    expect(frame.bounds).toEqual({ x: 90, y: 90, width: 70, height: 70 })
  })

  it('when any frame-type element exists, only frames contribute', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    // A plain rect.
    store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      roundness: 0,
    })
    // A frame element.
    const frameId = store.create({
      type: 'frame',
      x: 0,
      y: 0,
      width: 100,
      height: 100,
      name: 'F1',
      childIds: [],
    })
    const frames = computeFrames(store.list())
    expect(frames).toHaveLength(1)
    expect(frames[0].id).toBe(frameId)
  })
})

describe('viewportForBounds', () => {
  it('fits bounds into the canvas at the limiting axis scale', () => {
    // Square bounds 100x100 into a 200x400 canvas → sx=2, sy=4, scale=2.
    const vp = viewportForBounds(
      { x: 0, y: 0, width: 100, height: 100 },
      200,
      400,
    )
    expect(vp.scale).toBe(2)
  })

  it('centres the bounds inside the canvas', () => {
    // 100x100 bounds at (0,0) into a 200x200 canvas → scale=2, bounds
    // fill exactly, scroll = 0.
    const vp = viewportForBounds(
      { x: 0, y: 0, width: 100, height: 100 },
      200,
      200,
    )
    expect(vp.scrollX).toBe(0)
    expect(vp.scrollY).toBe(0)

    // 100x100 into 300x200 → scale=2, bounds width=200 screen px, canvas
    // is 300 wide → 50 px slack each side in world units = 25. Shift
    // scrollX left by 25 so the bounds sit centred.
    const vp2 = viewportForBounds(
      { x: 0, y: 0, width: 100, height: 100 },
      300,
      200,
    )
    expect(vp2.scale).toBe(2)
    expect(vp2.scrollX).toBe(-25)
    expect(vp2.scrollY).toBe(0)
  })

  it('clamps the computed scale to the legal range', () => {
    // Huge canvas + tiny bounds → scale would be enormous → clamped
    // to MAX_SCALE (30).
    const vp = viewportForBounds(
      { x: 0, y: 0, width: 1, height: 1 },
      10_000,
      10_000,
    )
    expect(vp.scale).toBeLessThanOrEqual(30)
  })

  it('returns an unscaled identity on degenerate bounds or canvas', () => {
    expect(
      viewportForBounds({ x: 5, y: 6, width: 0, height: 0 }, 100, 100),
    ).toEqual({ scale: 1, scrollX: 5, scrollY: 6 })
    expect(
      viewportForBounds({ x: 5, y: 6, width: 10, height: 10 }, 0, 100),
    ).toEqual({ scale: 1, scrollX: 5, scrollY: 6 })
  })
})

describe('advanceFrame', () => {
  it('advances within bounds', () => {
    expect(advanceFrame(0, 3, 1)).toBe(1)
    expect(advanceFrame(1, 3, 1)).toBe(2)
  })

  it('clamps past the last frame', () => {
    expect(advanceFrame(2, 3, 1)).toBe(2)
  })

  it('clamps before the first frame', () => {
    expect(advanceFrame(0, 3, -1)).toBe(0)
  })

  it('returns 0 on an empty list', () => {
    expect(advanceFrame(0, 0, 1)).toBe(0)
    expect(advanceFrame(0, 0, -1)).toBe(0)
  })
})
