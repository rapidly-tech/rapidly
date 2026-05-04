import { describe, expect, it } from 'vitest'

import {
  _resetLassoStateForTests,
  currentLassoPath,
  elementsInsidePolygon,
  lassoTool,
  pointInPolygon,
} from './lasso'
import type { ToolCtx } from './types'

describe('pointInPolygon', () => {
  // Square 0..10 × 0..10
  const square = [0, 0, 10, 0, 10, 10, 0, 10]

  it('returns true for points inside a square', () => {
    expect(pointInPolygon(5, 5, square)).toBe(true)
    expect(pointInPolygon(1, 1, square)).toBe(true)
    expect(pointInPolygon(9, 9, square)).toBe(true)
  })

  it('returns false for points outside a square', () => {
    expect(pointInPolygon(-1, 5, square)).toBe(false)
    expect(pointInPolygon(11, 5, square)).toBe(false)
    expect(pointInPolygon(5, -1, square)).toBe(false)
    expect(pointInPolygon(5, 11, square)).toBe(false)
  })

  it('returns false for degenerate polygons (< 3 vertices)', () => {
    expect(pointInPolygon(0, 0, [])).toBe(false)
    expect(pointInPolygon(0, 0, [1, 1])).toBe(false)
    expect(pointInPolygon(0, 0, [1, 1, 2, 2])).toBe(false)
  })

  it('classifies points consistently for self-intersecting polygons', () => {
    // Bowtie traced (0,0) → (10,10) → (10,0) → (0,10). The two
    // triangle bodies are inside; the path is well-defined under the
    // crossing-number rule. Verify each triangle lobe correctly
    // tests inside, and a point clearly outside both lobes is out.
    const bowtie = [0, 0, 10, 10, 10, 0, 0, 10]
    expect(pointInPolygon(8, 5, bowtie)).toBe(true) // right lobe
    expect(pointInPolygon(2, 5, bowtie)).toBe(true) // left lobe
    expect(pointInPolygon(-1, 5, bowtie)).toBe(false) // beyond left
    expect(pointInPolygon(11, 5, bowtie)).toBe(false) // beyond right
  })

  it('handles concave polygons (the whole point of lasso)', () => {
    // C-shape — points inside the indentation should be outside.
    const cShape = [0, 0, 10, 0, 10, 4, 4, 4, 4, 6, 10, 6, 10, 10, 0, 10]
    expect(pointInPolygon(2, 5, cShape)).toBe(true) // inside the C body
    expect(pointInPolygon(7, 5, cShape)).toBe(false) // inside the indent
  })
})

describe('elementsInsidePolygon', () => {
  // Helper to build a fake ToolCtx around a list of element AABBs.
  function makeCtx(
    elements: Array<{
      id: string
      x: number
      y: number
      width: number
      height: number
    }>,
  ): ToolCtx {
    return {
      store: {
        list: () => elements,
      },
      // Unused by the function under test
    } as unknown as ToolCtx
  }

  const square = [0, 0, 100, 0, 100, 100, 0, 100]

  it('returns ids whose centres lie inside the polygon', () => {
    const ctx = makeCtx([
      { id: 'a', x: 10, y: 10, width: 20, height: 20 }, // centre 20,20 — in
      { id: 'b', x: 200, y: 200, width: 20, height: 20 }, // 210,210 — out
      { id: 'c', x: 80, y: 80, width: 20, height: 20 }, // 90,90 — in
    ])
    const ids = elementsInsidePolygon(ctx, square)
    expect(ids.sort()).toEqual(['a', 'c'])
  })

  it('returns empty for degenerate polygons', () => {
    const ctx = makeCtx([{ id: 'a', x: 10, y: 10, width: 20, height: 20 }])
    expect(elementsInsidePolygon(ctx, [0, 0, 1, 1])).toEqual([])
  })

  it('uses element centre — not AABB intersection — as the rule', () => {
    // Element overlaps the polygon area-wise but its centre is outside.
    // Centre-rule says "exclude"; AABB-rule would say "include".
    const ctx = makeCtx([
      { id: 'edge-overlap', x: 90, y: 90, width: 30, height: 30 }, // centre 105,105 — out
    ])
    expect(elementsInsidePolygon(ctx, square)).toEqual([])
  })
})

describe('lassoTool', () => {
  it('exposes the canonical tool shape', () => {
    expect(lassoTool.id).toBe('lasso')
    expect(typeof lassoTool.cursor).toBe('string')
    expect(typeof lassoTool.onPointerDown).toBe('function')
    expect(typeof lassoTool.onPointerMove).toBe('function')
    expect(typeof lassoTool.onPointerUp).toBe('function')
    expect(typeof lassoTool.onCancel).toBe('function')
  })

  it('currentLassoPath() returns null when no gesture is active', () => {
    _resetLassoStateForTests()
    expect(currentLassoPath()).toBeNull()
  })
})
