/**
 * Zoom-to-fit / zoom-to-selection — pinned behaviour:
 *
 * - Union bbox math is correct for multiple elements.
 * - ``viewportToFitBounds`` centres the rect in the canvas.
 * - Scale is the SMALLER fit ratio (so the rect always fits).
 * - Padding is honoured on all sides.
 * - Empty input returns ``null`` (caller decides fallback).
 * - Degenerate (zero-area) bounds use the caller's fallback scale.
 * - Scale clamps to MIN_SCALE / MAX_SCALE.
 */

import { describe, expect, it } from 'vitest'

import type { CollabElement } from './elements'
import { MAX_SCALE, MIN_SCALE, viewportToFitBounds } from './viewport'
import {
  unionBoundsForElements,
  zoomToFit,
  zoomToSelection,
} from './zoom-to-fit'

function rect(
  id: string,
  x: number,
  y: number,
  width: number,
  height: number,
): CollabElement {
  return {
    id,
    type: 'rect',
    x,
    y,
    width,
    height,
    angle: 0,
    zIndex: 0,
    groupIds: [],
    strokeColor: '#000',
    fillColor: 'transparent',
    fillStyle: 'solid',
    strokeWidth: 1,
    strokeStyle: 'solid',
    roughness: 0,
    roundness: 0,
    opacity: 1,
    seed: 1,
    version: 1,
    locked: false,
  } as CollabElement
}

describe('unionBoundsForElements', () => {
  it('returns null for empty input', () => {
    expect(unionBoundsForElements([])).toBeNull()
  })

  it('computes union bbox across multiple rects', () => {
    const els = [rect('a', 10, 20, 30, 40), rect('b', 100, 5, 50, 50)]
    expect(unionBoundsForElements(els)).toEqual({
      x: 10,
      y: 5,
      width: 140,
      height: 55,
    })
  })

  it('matches a single-element bbox exactly', () => {
    expect(unionBoundsForElements([rect('a', 5, 5, 10, 10)])).toEqual({
      x: 5,
      y: 5,
      width: 10,
      height: 10,
    })
  })
})

describe('viewportToFitBounds', () => {
  it('centres the rect in the canvas', () => {
    // 100x100 rect at world (0,0); canvas 600x400; padding 24.
    const vp = viewportToFitBounds(
      { x: 0, y: 0, width: 100, height: 100 },
      600,
      400,
    )
    // Centre of bounds: (50,50). Centre of canvas / scale should land there.
    const centreScreenX = 600 / 2
    const centreScreenY = 400 / 2
    const centreWorldX = vp.scrollX + centreScreenX / vp.scale
    const centreWorldY = vp.scrollY + centreScreenY / vp.scale
    expect(centreWorldX).toBeCloseTo(50)
    expect(centreWorldY).toBeCloseTo(50)
  })

  it('uses the smaller fit ratio so the rect always fits', () => {
    // Wide rect (1000x10) on a narrow canvas → x is the limiting axis.
    const vp = viewportToFitBounds(
      { x: 0, y: 0, width: 1000, height: 10 },
      600,
      400,
      { padding: 0 },
    )
    // Without padding: scale = min(600/1000, 400/10) = 0.6.
    expect(vp.scale).toBeCloseTo(0.6)
  })

  it('honours padding on all sides', () => {
    const vp = viewportToFitBounds(
      { x: 0, y: 0, width: 100, height: 100 },
      600,
      400,
      { padding: 50 },
    )
    // innerW=500, innerH=300 → fitX=5, fitY=3 → min=3, clamped → 3.
    expect(vp.scale).toBeCloseTo(3)
  })

  it('clamps degenerate (zero-area) bounds to caller fallback', () => {
    const vp = viewportToFitBounds(
      { x: 50, y: 50, width: 0, height: 0 },
      600,
      400,
      { scale: 1.5 },
    )
    expect(vp.scale).toBe(1.5)
  })

  it('clamps an enormous bounds to MIN_SCALE', () => {
    const vp = viewportToFitBounds(
      { x: 0, y: 0, width: 1_000_000, height: 1_000_000 },
      600,
      400,
    )
    expect(vp.scale).toBe(MIN_SCALE)
  })

  it('clamps a tiny bounds to MAX_SCALE', () => {
    const vp = viewportToFitBounds(
      { x: 0, y: 0, width: 1, height: 1 },
      600,
      400,
      { padding: 0 },
    )
    expect(vp.scale).toBe(MAX_SCALE)
  })
})

describe('zoomToFit', () => {
  it('returns null for empty element list', () => {
    expect(zoomToFit([], 600, 400)).toBeNull()
  })

  it('produces a viewport matching unionBoundsForElements', () => {
    const els = [rect('a', 0, 0, 100, 100), rect('b', 200, 0, 100, 100)]
    const vp = zoomToFit(els, 600, 400)!
    // Bounds: x=[0,300], y=[0,100]. Centre: (150, 50).
    const centreWorldX = vp.scrollX + 600 / (2 * vp.scale)
    const centreWorldY = vp.scrollY + 400 / (2 * vp.scale)
    expect(centreWorldX).toBeCloseTo(150)
    expect(centreWorldY).toBeCloseTo(50)
  })
})

describe('zoomToSelection', () => {
  it('returns null when selection is empty', () => {
    const els = [rect('a', 0, 0, 100, 100)]
    expect(zoomToSelection(els, new Set(), 600, 400)).toBeNull()
  })

  it('returns null when selected ids are not in the element list', () => {
    const els = [rect('a', 0, 0, 100, 100)]
    expect(zoomToSelection(els, new Set(['ghost']), 600, 400)).toBeNull()
  })

  it('fits only the selected elements (ignores non-selected)', () => {
    const els = [
      rect('a', 0, 0, 100, 100), // selected
      rect('b', 1000, 1000, 100, 100), // distant, NOT selected
    ]
    const vp = zoomToSelection(els, new Set(['a']), 600, 400)!
    // Centre on a's centre (50, 50), not on the union including b.
    const centreWorldX = vp.scrollX + 600 / (2 * vp.scale)
    const centreWorldY = vp.scrollY + 400 / (2 * vp.scale)
    expect(centreWorldX).toBeCloseTo(50)
    expect(centreWorldY).toBeCloseTo(50)
  })
})
