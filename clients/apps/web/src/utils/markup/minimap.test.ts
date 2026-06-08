import { describe, expect, it } from 'vitest'

import type { CollabElement } from './elements'
import {
  centreViewportOn,
  computeSceneBounds,
  minimapPointToWorld,
  projectRect,
  projectToMinimap,
  projectViewportRect,
} from './minimap'

const baseFields = {
  angle: 0,
  zIndex: 0,
  groupIds: [],
  strokeColor: '#000',
  fillColor: 'transparent',
  fillStyle: 'none' as const,
  strokeWidth: 1,
  strokeStyle: 'solid' as const,
  roughness: 0 as const,
  opacity: 100,
  seed: 1,
  version: 0,
  locked: false,
}

const rect = (x: number, y: number, w: number, h: number): CollabElement =>
  ({
    type: 'rect',
    id: `${x},${y}`,
    x,
    y,
    width: w,
    height: h,
    roundness: 0,
    ...baseFields,
  }) as CollabElement

describe('computeSceneBounds', () => {
  it('returns a synthetic 1×1 rect for an empty scene', () => {
    expect(computeSceneBounds([])).toEqual({
      minX: 0,
      minY: 0,
      maxX: 1,
      maxY: 1,
    })
  })

  it('encloses a single element exactly', () => {
    expect(computeSceneBounds([rect(10, 20, 30, 40)])).toEqual({
      minX: 10,
      minY: 20,
      maxX: 40,
      maxY: 60,
    })
  })

  it('takes the union of multiple elements', () => {
    const els = [rect(0, 0, 10, 10), rect(50, 30, 20, 40)]
    expect(computeSceneBounds(els)).toEqual({
      minX: 0,
      minY: 0,
      maxX: 70,
      maxY: 70,
    })
  })

  it('handles negative coordinates', () => {
    expect(computeSceneBounds([rect(-50, -30, 10, 10)])).toEqual({
      minX: -50,
      minY: -30,
      maxX: -40,
      maxY: -20,
    })
  })
})

describe('projectToMinimap', () => {
  it('preserves aspect ratio by letterboxing the shorter axis', () => {
    // Square world → wide minimap should letterbox horizontally.
    const proj = projectToMinimap(
      { minX: 0, minY: 0, maxX: 100, maxY: 100 },
      200,
      100,
      0,
    )
    expect(proj.scale).toBe(1) // 100 world / 100 px
    // The world is 100 wide → 100 px wide on the minimap. Centred in
    // 200 px: offsetX = 50.
    expect(proj.offsetX).toBe(50)
    expect(proj.offsetY).toBe(0)
  })

  it('respects padding by shrinking the usable area', () => {
    const proj = projectToMinimap(
      { minX: 0, minY: 0, maxX: 100, maxY: 100 },
      120,
      120,
      10,
    )
    // Usable area is 100×100 (120 - 2*10), so scale = 1 and the
    // projection sits exactly at the padding offset.
    expect(proj.scale).toBe(1)
    expect(proj.offsetX).toBe(10)
    expect(proj.offsetY).toBe(10)
  })

  it('does not divide by zero on a degenerate scene', () => {
    const proj = projectToMinimap(
      { minX: 5, minY: 5, maxX: 5, maxY: 5 },
      100,
      100,
      0,
    )
    expect(Number.isFinite(proj.scale)).toBe(true)
  })
})

describe('projectRect', () => {
  it('projects a world rect through the minimap transform', () => {
    const proj = projectToMinimap(
      { minX: 0, minY: 0, maxX: 100, maxY: 100 },
      100,
      100,
      0,
    )
    const r = projectRect({ x: 10, y: 20, width: 30, height: 40 }, proj)
    // scale = 1, offsets = 0 → identity.
    expect(r).toEqual({ x: 10, y: 20, width: 30, height: 40 })
  })

  it('translates by the projection offset', () => {
    // Scene starts at (50, 50) instead of origin.
    const proj = projectToMinimap(
      { minX: 50, minY: 50, maxX: 150, maxY: 150 },
      100,
      100,
      0,
    )
    const r = projectRect({ x: 60, y: 70, width: 10, height: 20 }, proj)
    // Element offset within the scene is (10, 20); scale = 1.
    expect(r).toEqual({ x: 10, y: 20, width: 10, height: 20 })
  })
})

describe('projectViewportRect', () => {
  it('projects the visible viewport based on canvas size and zoom', () => {
    const proj = projectToMinimap(
      { minX: 0, minY: 0, maxX: 1000, maxY: 1000 },
      100,
      100,
      0,
    )
    // scale = 10 world units / minimap pixel.
    const vpRect = projectViewportRect(
      { scale: 1, scrollX: 200, scrollY: 100 },
      400,
      300,
      proj,
    )
    expect(vpRect.x).toBeCloseTo(20)
    expect(vpRect.y).toBeCloseTo(10)
    expect(vpRect.width).toBeCloseTo(40)
    expect(vpRect.height).toBeCloseTo(30)
  })

  it('shrinks the viewport rect as the zoom rises', () => {
    const proj = projectToMinimap(
      { minX: 0, minY: 0, maxX: 1000, maxY: 1000 },
      100,
      100,
      0,
    )
    const a = projectViewportRect(
      { scale: 1, scrollX: 0, scrollY: 0 },
      400,
      300,
      proj,
    )
    const b = projectViewportRect(
      { scale: 2, scrollX: 0, scrollY: 0 },
      400,
      300,
      proj,
    )
    // Doubled zoom → half-size viewport rect on the minimap.
    expect(b.width).toBeCloseTo(a.width / 2)
    expect(b.height).toBeCloseTo(a.height / 2)
  })
})

describe('minimapPointToWorld', () => {
  it('inverts projectRect for the position component', () => {
    const proj = projectToMinimap(
      { minX: 100, minY: 200, maxX: 300, maxY: 400 },
      100,
      100,
      0,
    )
    // Click at (10, 10) in the minimap → world (200, 220) at scale 2.
    const world = minimapPointToWorld(10, 10, proj)
    expect(world.x).toBeCloseTo(120)
    expect(world.y).toBeCloseTo(220)
  })
})

describe('centreViewportOn', () => {
  it('computes a viewport that centres the canvas on the world point', () => {
    const next = centreViewportOn(
      { scale: 1, scrollX: 0, scrollY: 0 },
      500,
      300,
      400,
      200,
    )
    // (canvas/scale)/2 = (200, 100); scroll = world - that.
    expect(next.scrollX).toBe(300)
    expect(next.scrollY).toBe(200)
    expect(next.scale).toBe(1)
  })

  it('preserves the current zoom level', () => {
    const next = centreViewportOn(
      { scale: 2.5, scrollX: 0, scrollY: 0 },
      0,
      0,
      400,
      300,
    )
    expect(next.scale).toBe(2.5)
  })
})
