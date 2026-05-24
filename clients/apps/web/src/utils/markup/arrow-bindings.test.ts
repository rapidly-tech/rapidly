import { describe, expect, it } from 'vitest'

import {
  BIND_RADIUS_PX,
  collectBoundArrowPatches,
  findBinding,
  resolveBinding,
} from './arrow-bindings'
import {
  DEFAULT_FILL_COLOR,
  DEFAULT_FILL_STYLE,
  DEFAULT_OPACITY,
  DEFAULT_ROUGHNESS,
  DEFAULT_STROKE_COLOR,
  DEFAULT_STROKE_STYLE,
  DEFAULT_STROKE_WIDTH,
  type ArrowElement,
  type CollabElement,
  type RectElement,
} from './elements'

function rect(overrides: Partial<RectElement> = {}): RectElement {
  return {
    id: 'r1',
    type: 'rect',
    x: 100,
    y: 100,
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

describe('findBinding', () => {
  it('binds to the nearest edge midpoint when pointer is within radius', () => {
    const r = rect({ x: 0, y: 0, width: 100, height: 50 })
    const b = findBinding([r], 50, 5, 1)
    expect(b).not.toBeNull()
    expect(b?.elementId).toBe('r1')
    // Top-mid slot = 1/8.
    expect(b?.focus).toBeCloseTo(1 / 8, 4)
  })

  it('returns null when pointer is too far', () => {
    const r = rect({ x: 0, y: 0, width: 100, height: 50 })
    const b = findBinding([r], 500, 500, 1)
    expect(b).toBeNull()
  })

  it('picks the closest candidate among multiple', () => {
    const a = rect({ id: 'a', x: 0, y: 0, width: 50, height: 50 })
    const b = rect({ id: 'b', x: 200, y: 0, width: 50, height: 50 })
    // Cursor near b's nw corner.
    const binding = findBinding([a, b], 205, 5, 1)
    expect(binding?.elementId).toBe('b')
  })

  it('excludes the id passed in excludeId (self-binding guard)', () => {
    const r = rect({ x: 0, y: 0, width: 100, height: 50 })
    const b = findBinding([r], 50, 5, 1, 'r1')
    expect(b).toBeNull()
  })

  it('scales the radius with the viewport so bindings feel the same at any zoom', () => {
    const r = rect({ x: 0, y: 0, width: 100, height: 50 })
    // At scale 1, a pointer 20 world units away is outside the
    // ``BIND_RADIUS_PX / 1`` radius (12 world units).
    expect(findBinding([r], 50, 20, 1)).toBeNull()
    // At scale 0.25, the same 20 world units is inside the scaled
    // radius (12 / 0.25 = 48).
    expect(findBinding([r], 50, 20, 0.25)).not.toBeNull()
  })

  it('BIND_RADIUS_PX is a sensible default', () => {
    // Ops: regressions on this number have caused "arrows eat my
    // shape" complaints before. Pin it here so a drive-by tweak
    // shows up in review.
    expect(BIND_RADIUS_PX).toBe(12)
  })
})

describe('resolveBinding', () => {
  it('maps every focus slot to its perimeter point', () => {
    const r = rect({ x: 0, y: 0, width: 100, height: 50 })
    const cases: Array<[number, { x: number; y: number }]> = [
      [0, { x: 0, y: 0 }],
      [1 / 8, { x: 50, y: 0 }],
      [2 / 8, { x: 100, y: 0 }],
      [3 / 8, { x: 100, y: 25 }],
      [4 / 8, { x: 100, y: 50 }],
      [5 / 8, { x: 50, y: 50 }],
      [6 / 8, { x: 0, y: 50 }],
      [7 / 8, { x: 0, y: 25 }],
    ]
    for (const [focus, expected] of cases) {
      const got = resolveBinding(r, { elementId: 'r1', focus, gap: 0 })
      expect(got).toEqual(expected)
    }
  })

  it('tracks the shape as it moves', () => {
    const before = rect({ x: 0, y: 0, width: 100, height: 50 })
    const after = rect({ x: 500, y: 300, width: 100, height: 50 })
    const binding = { elementId: 'r1', focus: 3 / 8, gap: 0 }
    const pBefore = resolveBinding(before as CollabElement, binding)
    const pAfter = resolveBinding(after as CollabElement, binding)
    expect(pAfter.x - pBefore.x).toBe(500)
    expect(pAfter.y - pBefore.y).toBe(300)
  })

  it('tracks the shape as it resizes', () => {
    const small = rect({ x: 0, y: 0, width: 100, height: 50 })
    const big = rect({ x: 0, y: 0, width: 200, height: 100 })
    const binding = { elementId: 'r1', focus: 4 / 8, gap: 0 }
    // se-corner moves from (100,50) to (200,100) as the rect grows.
    expect(resolveBinding(small as CollabElement, binding)).toEqual({
      x: 100,
      y: 50,
    })
    expect(resolveBinding(big as CollabElement, binding)).toEqual({
      x: 200,
      y: 100,
    })
  })
})

function arrow(overrides: Partial<ArrowElement> = {}): ArrowElement {
  return {
    id: 'a1',
    type: 'arrow',
    x: 0,
    y: 0,
    width: 100,
    height: 0,
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
    points: [0, 0, 100, 0],
    startArrowhead: null,
    endArrowhead: 'triangle',
    ...overrides,
  }
}

describe('collectBoundArrowPatches', () => {
  it('updates an arrow whose start is bound to a moved rect', () => {
    // Rect at its new position (moved from (0,0) → (300,200)).
    const r = rect({
      id: 'r1',
      x: 300,
      y: 200,
      width: 100,
      height: 50,
    })
    // Arrow whose start was bound to r1's east midpoint; end is free.
    const a = arrow({
      id: 'a1',
      x: 100,
      y: 25,
      width: 200,
      height: 0,
      points: [0, 0, 200, 0],
      startBinding: { elementId: 'r1', focus: 3 / 8, gap: 0 },
      endBinding: undefined,
    })
    const patches = collectBoundArrowPatches([r, a], new Set(['r1']))
    expect(patches.length).toBe(1)
    const p = patches[0]
    // East midpoint of the new rect position: (400, 225).
    // End stayed at its old world coord: (100 + 200, 25 + 0) = (300, 25).
    const startX = 400
    const startY = 225
    const endX = 300
    const endY = 25
    expect(p.patch.x).toBe(Math.min(startX, endX))
    expect(p.patch.y).toBe(Math.min(startY, endY))
    expect(p.patch.width).toBe(Math.abs(endX - startX))
    expect(p.patch.height).toBe(Math.abs(endY - startY))
    // Start should be at (local 0, local 0) or wherever the AABB
    // origin is — just sanity-check that the world-space start from
    // the patch reconstructs.
    const worldStartX = p.patch.x + p.patch.points[0]
    const worldStartY = p.patch.y + p.patch.points[1]
    expect(worldStartX).toBe(startX)
    expect(worldStartY).toBe(startY)
  })

  it('updates an arrow bound at BOTH ends when one target moves', () => {
    const rA = rect({ id: 'rA', x: 0, y: 0, width: 50, height: 50 })
    const rB = rect({ id: 'rB', x: 200, y: 0, width: 50, height: 50 })
    const a = arrow({
      id: 'a1',
      startBinding: { elementId: 'rA', focus: 3 / 8, gap: 0 },
      endBinding: { elementId: 'rB', focus: 7 / 8, gap: 0 },
    })
    const patches = collectBoundArrowPatches([rA, rB, a], new Set(['rA']))
    expect(patches.length).toBe(1)
    // Start re-resolved against rA's east mid (50, 25).
    const worldStartX = patches[0].patch.x + patches[0].patch.points[0]
    const worldStartY = patches[0].patch.y + patches[0].patch.points[1]
    expect(worldStartX).toBe(50)
    expect(worldStartY).toBe(25)
    // End re-resolved against rB's west mid (200, 25).
    const worldEndX = patches[0].patch.x + patches[0].patch.points[2]
    const worldEndY = patches[0].patch.y + patches[0].patch.points[3]
    expect(worldEndX).toBe(200)
    expect(worldEndY).toBe(25)
  })

  it('ignores arrows with no bindings to any changed element', () => {
    const r = rect({ id: 'r1', x: 0, y: 0, width: 50, height: 50 })
    const a = arrow({
      id: 'a1',
      startBinding: undefined,
      endBinding: undefined,
    })
    const patches = collectBoundArrowPatches([r, a], new Set(['r1']))
    expect(patches).toEqual([])
  })

  it('returns empty patch list when no ids changed', () => {
    expect(collectBoundArrowPatches([], new Set())).toEqual([])
  })
})
