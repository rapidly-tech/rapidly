/**
 * Flip operations — pinned behaviour:
 *
 * - Single-element flip mirrors the element across its own centre →
 *   element stays in place; angle is negated (h) or pi-minus (v).
 * - Multi-element flip mirrors across the bounding-box centre line →
 *   relative positions flip too (so a "before/after" diagram becomes
 *   "after/before").
 * - Linear / freedraw elements have their per-point coords flipped
 *   in element-local space (flat array preserved, x at i, y at i+1).
 * - Locked elements are skipped.
 * - The whole operation is one Yjs transaction so undo is single-step.
 */

import { beforeEach, describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import { createElementStore, type ElementStore } from './element-store'
import { flip, flipHorizontal, flipVertical } from './flip'

function makeStore(): ElementStore {
  return createElementStore(new Y.Doc())
}

describe('flipHorizontal', () => {
  let store: ElementStore
  beforeEach(() => {
    store = makeStore()
  })

  it('mirrors a single element in place across its own centre', () => {
    store.create({ id: 'r', type: 'rect', x: 100, y: 50, width: 40, height: 20 })
    flipHorizontal(store, new Set(['r']))
    const after = store.get('r')!
    // Centre at (120, 60); flip across centre → element keeps position.
    expect(after.x).toBe(100)
    expect(after.y).toBe(50)
  })

  it('mirrors multiple elements across the union bbox mid-x', () => {
    store.create({ id: 'a', type: 'rect', x: 0, y: 0, width: 20, height: 20 })
    store.create({ id: 'b', type: 'rect', x: 80, y: 0, width: 20, height: 20 })
    // Union bbox: x=[0,100], pivot=50.
    flipHorizontal(store, new Set(['a', 'b']))
    // a centre 10 → flip to 90 → x = 80; b centre 90 → flip to 10 → x = 0.
    expect(store.get('a')!.x).toBe(80)
    expect(store.get('b')!.x).toBe(0)
  })

  it('negates angle on horizontal flip', () => {
    store.create({
      id: 'r',
      type: 'rect',
      x: 0,
      y: 0,
      width: 20,
      height: 20,
      angle: Math.PI / 4,
    })
    flipHorizontal(store, new Set(['r']))
    expect(store.get('r')!.angle).toBeCloseTo(-Math.PI / 4)
  })

  it('mirrors linear-element points in element-local space', () => {
    store.create({
      id: 'l',
      type: 'line',
      x: 0,
      y: 0,
      width: 100,
      height: 50,
      points: [0, 0, 100, 50],
    })
    flipHorizontal(store, new Set(['l']))
    const after = store.get('l')!
    if (after.type !== 'line') throw new Error('expected line element')
    expect(after.points).toEqual([100, 0, 0, 50])
  })

  it('mirrors freedraw points (3-stride)', () => {
    store.create({
      id: 'p',
      type: 'freedraw',
      x: 0,
      y: 0,
      width: 100,
      height: 50,
      points: [0, 10, 0.5, 100, 40, 0.8],
      simulatePressure: false,
    })
    flipHorizontal(store, new Set(['p']))
    const after = store.get('p')!
    if (after.type !== 'freedraw') throw new Error('expected freedraw element')
    // x at i=0 (was 0 → 100), x at i=3 (was 100 → 0). Pressures unchanged.
    expect(after.points).toEqual([100, 10, 0.5, 0, 40, 0.8])
  })

  it('skips locked elements', () => {
    store.create({
      id: 'r',
      type: 'rect',
      x: 100,
      y: 50,
      width: 40,
      height: 20,
      locked: true,
    })
    const flipped = flipHorizontal(store, new Set(['r']))
    expect(flipped).toBe(0)
  })

  it('returns 0 on empty selection', () => {
    expect(flipHorizontal(store, new Set())).toBe(0)
  })
})

describe('flipVertical', () => {
  let store: ElementStore
  beforeEach(() => {
    store = makeStore()
  })

  it('mirrors across union bbox mid-y for multi-selection', () => {
    store.create({ id: 'a', type: 'rect', x: 0, y: 0, width: 20, height: 20 })
    store.create({ id: 'b', type: 'rect', x: 0, y: 80, width: 20, height: 20 })
    // bbox y=[0,100], pivot=50.
    flipVertical(store, new Set(['a', 'b']))
    expect(store.get('a')!.y).toBe(80)
    expect(store.get('b')!.y).toBe(0)
  })

  it('rotates angle by pi-minus', () => {
    store.create({
      id: 'r',
      type: 'rect',
      x: 0,
      y: 0,
      width: 20,
      height: 20,
      angle: 0.5,
    })
    flipVertical(store, new Set(['r']))
    expect(store.get('r')!.angle).toBeCloseTo(Math.PI - 0.5)
  })
})

describe('flip atomicity', () => {
  it('runs in a single transaction (undo is single-step)', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    store.create({ id: 'a', type: 'rect', x: 0, y: 0, width: 20, height: 20 })
    store.create({ id: 'b', type: 'rect', x: 50, y: 0, width: 20, height: 20 })

    let txCount = 0
    doc.on('afterTransaction', () => {
      txCount++
    })

    flip(store, new Set(['a', 'b']), 'horizontal')

    // Exactly one transaction (the flip), not one per element.
    expect(txCount).toBe(1)
  })
})
