import { describe, expect, it } from 'vitest'

import type { EllipseElement, RectElement } from '../elements'
import {
  DEFAULT_FILL_COLOR,
  DEFAULT_FILL_STYLE,
  DEFAULT_OPACITY,
  DEFAULT_ROUGHNESS,
  DEFAULT_STROKE_COLOR,
  DEFAULT_STROKE_STYLE,
  DEFAULT_STROKE_WIDTH,
} from '../elements'
import { adapterFor, ellipsePath, rectPath } from './index'

function baseRect(overrides: Partial<RectElement> = {}): RectElement {
  return {
    id: 'r1',
    type: 'rect',
    x: 0,
    y: 0,
    width: 100,
    height: 50,
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

function baseEllipse(overrides: Partial<EllipseElement> = {}): EllipseElement {
  return {
    id: 'e1',
    type: 'ellipse',
    x: 0,
    y: 0,
    width: 80,
    height: 40,
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
    ...overrides,
  }
}

describe('shape adapters', () => {
  it('adapterFor resolves rect and ellipse', () => {
    expect(adapterFor(baseRect())).not.toBeNull()
    expect(adapterFor(baseEllipse())).not.toBeNull()
  })

  it('adapterFor resolves an adapter for every concrete element type', () => {
    // Frame + embed both ship now; the registry should have full
    // coverage of the discriminated union.
    expect(adapterFor({ ...baseRect(), type: 'frame' } as never)).not.toBeNull()
    expect(adapterFor({ ...baseRect(), type: 'embed' } as never)).not.toBeNull()
  })

  it('rectPath produces a Path2D that can be hit-tested', () => {
    // jsdom's CanvasRenderingContext2D implements isPointInPath, which
    // is all we need to validate the path shape.
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')
    if (!ctx) {
      // Some headless environments ship without canvas 2D — skip.
      return
    }
    const el = baseRect({ width: 100, height: 50 })
    const path = rectPath(el)
    expect(ctx.isPointInPath(path, 50, 25)).toBe(true)
    expect(ctx.isPointInPath(path, 150, 25)).toBe(false)
  })

  it('rectPath clamps huge roundness against the rect size', () => {
    // A 100×50 rect asked for roundness 200 must still render — the
    // clamp brings it to 25 (half the shortest edge) and the path
    // still contains the centre.
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const el = baseRect({ width: 100, height: 50, roundness: 200 })
    const path = rectPath(el)
    expect(ctx.isPointInPath(path, 50, 25)).toBe(true)
  })

  it('ellipsePath hit-tests centre in, corners out', () => {
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const el = baseEllipse({ width: 80, height: 40 })
    const path = ellipsePath(el)
    // Centre: inside.
    expect(ctx.isPointInPath(path, 40, 20)).toBe(true)
    // Top-left corner of the bounding box: outside an ellipse.
    expect(ctx.isPointInPath(path, 0, 0)).toBe(false)
  })
})
