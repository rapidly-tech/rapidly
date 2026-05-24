import { describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import { createElementStore } from './element-store'
import {
  rotate90Clockwise,
  rotate90CounterClockwise,
  rotateBy,
} from './rotate-by'

const baseRect = (over: object = {}) => ({
  type: 'rect' as const,
  x: 0,
  y: 0,
  width: 10,
  height: 10,
  roundness: 0,
  angle: 0,
  ...over,
})

const TWO_PI = Math.PI * 2

describe('rotateBy', () => {
  it('adds the delta to the element angle', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect({ angle: 0 }))
    rotateBy(store, new Set([id]), Math.PI / 4)
    expect(store.get(id)?.angle).toBeCloseTo(Math.PI / 4)
  })

  it('wraps into [0, 2π)', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect({ angle: Math.PI * 1.5 }))
    rotateBy(store, new Set([id]), Math.PI) // 1.5π + π = 2.5π → 0.5π
    expect(store.get(id)?.angle).toBeCloseTo(Math.PI / 2)
  })

  it('handles negative deltas symmetrically', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect({ angle: 0 }))
    rotateBy(store, new Set([id]), -Math.PI / 2)
    expect(store.get(id)?.angle).toBeCloseTo((TWO_PI - Math.PI / 2) % TWO_PI)
  })

  it('rotates each element in a multi-selection independently', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create(baseRect({ angle: 0 }))
    const b = store.create(baseRect({ angle: Math.PI / 2 }))
    rotateBy(store, new Set([a, b]), Math.PI / 4)
    expect(store.get(a)?.angle).toBeCloseTo(Math.PI / 4)
    expect(store.get(b)?.angle).toBeCloseTo(Math.PI / 2 + Math.PI / 4)
  })

  it('skips locked elements', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect({ angle: 0, locked: true }))
    rotateBy(store, new Set([id]), Math.PI / 2)
    expect(store.get(id)?.angle).toBe(0)
  })

  it('is a no-op for an empty selection', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect({ angle: 0 }))
    rotateBy(store, new Set(), Math.PI / 2)
    expect(store.get(id)?.angle).toBe(0)
  })

  it('is a no-op when the delta is non-finite', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect({ angle: 0 }))
    rotateBy(store, new Set([id]), Number.NaN)
    expect(store.get(id)?.angle).toBe(0)
  })

  it('skips ghost ids without throwing', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect({ angle: 0 }))
    expect(() =>
      rotateBy(store, new Set([id, 'ghost']), Math.PI / 2),
    ).not.toThrow()
    expect(store.get(id)?.angle).toBeCloseTo(Math.PI / 2)
  })
})

describe('rotate90Clockwise / rotate90CounterClockwise', () => {
  it('CW adds π/2', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect({ angle: 0 }))
    rotate90Clockwise(store, new Set([id]))
    expect(store.get(id)?.angle).toBeCloseTo(Math.PI / 2)
  })

  it('CCW subtracts π/2 (wraps to 3π/2)', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect({ angle: 0 }))
    rotate90CounterClockwise(store, new Set([id]))
    expect(store.get(id)?.angle).toBeCloseTo((Math.PI * 3) / 2)
  })

  it('four CWs return the original orientation', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect({ angle: 0 }))
    rotate90Clockwise(store, new Set([id]))
    rotate90Clockwise(store, new Set([id]))
    rotate90Clockwise(store, new Set([id]))
    rotate90Clockwise(store, new Set([id]))
    expect(store.get(id)?.angle).toBeCloseTo(0)
  })

  it('CW + CCW round-trips', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect({ angle: Math.PI / 6 }))
    rotate90Clockwise(store, new Set([id]))
    rotate90CounterClockwise(store, new Set([id]))
    expect(store.get(id)?.angle).toBeCloseTo(Math.PI / 6)
  })
})
