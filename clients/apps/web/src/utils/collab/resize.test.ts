import { describe, expect, it } from 'vitest'

import {
  DEFAULT_FILL_COLOR,
  DEFAULT_FILL_STYLE,
  DEFAULT_OPACITY,
  DEFAULT_ROUGHNESS,
  DEFAULT_STROKE_COLOR,
  DEFAULT_STROKE_STYLE,
  DEFAULT_STROKE_WIDTH,
  type RectElement,
} from './elements'
import {
  anchorFrom,
  applyResize,
  cursorForHandle,
  handleRotatedPositions,
  handleWorldPositions,
  hitHandle,
  rotatePoint,
} from './resize'
import { makeViewport } from './viewport'

function baseRect(overrides: Partial<RectElement> = {}): RectElement {
  return {
    id: 'r',
    type: 'rect',
    x: 100,
    y: 50,
    width: 200,
    height: 100,
    angle: 0,
    zIndex: 0,
    groupIds: [],
    strokeColor: DEFAULT_STROKE_COLOR,
    fillColor: DEFAULT_FILL_COLOR,
    fillStyle: DEFAULT_FILL_STYLE,
    strokeWidth: DEFAULT_STROKE_WIDTH,
    strokeStyle: DEFAULT_STROKE_STYLE,
    roughness: DEFAULT_ROUGHNESS,
    opacity: DEFAULT_OPACITY,
    seed: 1,
    version: 1,
    locked: false,
    roundness: 0,
    ...overrides,
  }
}

describe('handleWorldPositions', () => {
  it('places handles at corners + edge midpoints', () => {
    const h = handleWorldPositions(baseRect())
    expect(h.nw).toEqual({ x: 100, y: 50 })
    expect(h.ne).toEqual({ x: 300, y: 50 })
    expect(h.sw).toEqual({ x: 100, y: 150 })
    expect(h.se).toEqual({ x: 300, y: 150 })
    expect(h.n).toEqual({ x: 200, y: 50 })
    expect(h.s).toEqual({ x: 200, y: 150 })
    expect(h.e).toEqual({ x: 300, y: 100 })
    expect(h.w).toEqual({ x: 100, y: 100 })
  })
})

describe('rotatePoint', () => {
  it('is a no-op at angle 0', () => {
    expect(rotatePoint(5, 7, 0, 0, 0)).toEqual({ x: 5, y: 7 })
  })

  it('rotates 90° around origin', () => {
    const r = rotatePoint(1, 0, 0, 0, Math.PI / 2)
    expect(r.x).toBeCloseTo(0, 10)
    expect(r.y).toBeCloseTo(1, 10)
  })

  it('rotates 180° around the element centre', () => {
    const r = rotatePoint(0, 0, 100, 50, Math.PI)
    expect(r.x).toBeCloseTo(200, 10)
    expect(r.y).toBeCloseTo(100, 10)
  })
})

describe('handleRotatedPositions', () => {
  it('at angle 0 matches the raw world positions', () => {
    const raw = handleWorldPositions(baseRect())
    const rot = handleRotatedPositions(baseRect())
    for (const k of Object.keys(raw) as Array<keyof typeof raw>) {
      expect(rot[k]).toEqual(raw[k])
    }
  })
})

describe('hitHandle', () => {
  it('hits the nw handle when the cursor is at its screen projection', () => {
    const el = baseRect()
    const vp = makeViewport({ scale: 1, scrollX: 0, scrollY: 0 })
    expect(hitHandle(el, vp, 100, 50)).toBe('nw')
  })

  it('returns null when far from every handle', () => {
    const el = baseRect()
    const vp = makeViewport()
    expect(hitHandle(el, vp, 1000, 1000)).toBeNull()
  })

  it('scales hit radius with the viewport so handle feels the same at any zoom', () => {
    const el = baseRect()
    const vpA = makeViewport({ scale: 1 })
    const vpB = makeViewport({ scale: 4 })
    // Same offset in screen pixels — hits in both.
    expect(hitHandle(el, vpA, 105, 55)).toBe('nw')
    expect(hitHandle(el, vpB, 405, 205)).toBe('nw')
  })
})

describe('cursorForHandle', () => {
  it('maps every handle to a CSS directional cursor', () => {
    expect(cursorForHandle('n')).toBe('ns-resize')
    expect(cursorForHandle('s')).toBe('ns-resize')
    expect(cursorForHandle('e')).toBe('ew-resize')
    expect(cursorForHandle('w')).toBe('ew-resize')
    expect(cursorForHandle('nw')).toBe('nwse-resize')
    expect(cursorForHandle('se')).toBe('nwse-resize')
    expect(cursorForHandle('ne')).toBe('nesw-resize')
    expect(cursorForHandle('sw')).toBe('nesw-resize')
  })
})

describe('applyResize', () => {
  const anchor = anchorFrom(baseRect())

  it('se handle grows both width and height', () => {
    expect(applyResize(anchor, 'se', 50, 20)).toEqual({
      x: 100,
      y: 50,
      width: 250,
      height: 120,
    })
  })

  it('nw handle moves origin + shrinks dimensions', () => {
    expect(applyResize(anchor, 'nw', 10, 5)).toEqual({
      x: 110,
      y: 55,
      width: 190,
      height: 95,
    })
  })

  it('n handle only changes y and height', () => {
    expect(applyResize(anchor, 'n', 99, 10)).toEqual({
      x: 100,
      y: 60,
      width: 200,
      height: 90,
    })
  })

  it('e handle only changes width', () => {
    expect(applyResize(anchor, 'e', 30, 99)).toEqual({
      x: 100,
      y: 50,
      width: 230,
      height: 100,
    })
  })

  it('dragging se past origin flips into a normalised positive rect', () => {
    // Drag se handle back past the anchor's nw corner.
    const flipped = applyResize(anchor, 'se', -300, -200)
    expect(flipped.width).toBeGreaterThan(0)
    expect(flipped.height).toBeGreaterThan(0)
    // New origin shifted up/left.
    expect(flipped.x).toBeLessThan(anchor.x)
    expect(flipped.y).toBeLessThan(anchor.y)
  })

  it('clamps below 1 world unit so the element stays hit-testable', () => {
    const tiny = applyResize(anchor, 'se', -anchor.width, -anchor.height)
    expect(tiny.width).toBeGreaterThanOrEqual(1)
    expect(tiny.height).toBeGreaterThanOrEqual(1)
  })
})
