/**
 * Align + distribute — pinned behaviour:
 *
 * - ``align`` snaps each element's bbox edge / centre to the union
 *   bbox edge along the requested axis.
 * - ``distribute`` keeps the first/last anchors in place and spaces
 *   interior elements so consecutive bounding-box gaps are equal.
 * - Locked elements are skipped.
 * - Single-element selection (or 0/1 elements after lock filter) is
 *   a no-op.
 * - Whole batch in one transaction → one undo step.
 */

import { beforeEach, describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import { align, distribute } from './align'
import { createElementStore, type ElementStore } from './element-store'

function makeStore(): ElementStore {
  return createElementStore(new Y.Doc())
}

describe('align', () => {
  let store: ElementStore
  beforeEach(() => {
    store = makeStore()
  })

  it('aligns left edges to the leftmost element', () => {
    store.create({ id: 'a', type: 'rect', x: 100, y: 0, width: 50, height: 20 })
    store.create({ id: 'b', type: 'rect', x: 30, y: 50, width: 40, height: 20 })
    store.create({
      id: 'c',
      type: 'rect',
      x: 200,
      y: 100,
      width: 30,
      height: 20,
    })
    align(store, new Set(['a', 'b', 'c']), 'left')
    expect(store.get('a')!.x).toBe(30)
    expect(store.get('b')!.x).toBe(30)
    expect(store.get('c')!.x).toBe(30)
  })

  it('aligns right edges to the rightmost element', () => {
    store.create({ id: 'a', type: 'rect', x: 0, y: 0, width: 50, height: 20 })
    store.create({ id: 'b', type: 'rect', x: 0, y: 0, width: 40, height: 20 })
    store.create({ id: 'c', type: 'rect', x: 100, y: 0, width: 30, height: 20 })
    align(store, new Set(['a', 'b', 'c']), 'right')
    // bbox.maxX = 130. Each element's right edge → 130.
    expect(store.get('a')!.x + store.get('a')!.width).toBe(130)
    expect(store.get('b')!.x + store.get('b')!.width).toBe(130)
    expect(store.get('c')!.x + store.get('c')!.width).toBe(130)
  })

  it('aligns centre-x to the midpoint of the union bbox', () => {
    store.create({ id: 'a', type: 'rect', x: 0, y: 0, width: 20, height: 20 })
    store.create({ id: 'b', type: 'rect', x: 100, y: 0, width: 20, height: 20 })
    // bbox.x [0,120], centre = 60.
    align(store, new Set(['a', 'b']), 'centreX')
    expect(store.get('a')!.x + store.get('a')!.width / 2).toBe(60)
    expect(store.get('b')!.x + store.get('b')!.width / 2).toBe(60)
  })

  it('aligns top edges', () => {
    store.create({ id: 'a', type: 'rect', x: 0, y: 50, width: 20, height: 20 })
    store.create({ id: 'b', type: 'rect', x: 0, y: 10, width: 20, height: 20 })
    align(store, new Set(['a', 'b']), 'top')
    expect(store.get('a')!.y).toBe(10)
    expect(store.get('b')!.y).toBe(10)
  })

  it('aligns bottom edges', () => {
    store.create({ id: 'a', type: 'rect', x: 0, y: 0, width: 20, height: 30 })
    store.create({ id: 'b', type: 'rect', x: 0, y: 50, width: 20, height: 20 })
    align(store, new Set(['a', 'b']), 'bottom')
    // bbox.maxY = 70. Bottom of each → 70.
    expect(store.get('a')!.y + store.get('a')!.height).toBe(70)
    expect(store.get('b')!.y + store.get('b')!.height).toBe(70)
  })

  it('skips locked elements', () => {
    store.create({ id: 'a', type: 'rect', x: 100, y: 0, width: 50, height: 20 })
    store.create({
      id: 'b',
      type: 'rect',
      x: 200,
      y: 0,
      width: 50,
      height: 20,
      locked: true,
    })
    align(store, new Set(['a', 'b']), 'left')
    // Locked b stays at 200; a moves alone (only 1 unlocked → no-op).
    expect(store.get('b')!.x).toBe(200)
    expect(store.get('a')!.x).toBe(100)
  })

  it('is a no-op for single-element selection', () => {
    store.create({ id: 'a', type: 'rect', x: 100, y: 0, width: 50, height: 20 })
    const moved = align(store, new Set(['a']), 'left')
    expect(moved).toBe(0)
    expect(store.get('a')!.x).toBe(100)
  })

  it('is a no-op for empty selection', () => {
    expect(align(store, new Set(), 'left')).toBe(0)
  })

  it('runs in one transaction (single undo step)', () => {
    const doc = new Y.Doc()
    const store2 = createElementStore(doc)
    store2.create({ id: 'a', type: 'rect', x: 0, y: 0, width: 20, height: 20 })
    store2.create({
      id: 'b',
      type: 'rect',
      x: 100,
      y: 0,
      width: 20,
      height: 20,
    })
    let txCount = 0
    doc.on('afterTransaction', () => {
      txCount++
    })
    align(store2, new Set(['a', 'b']), 'left')
    expect(txCount).toBe(1)
  })
})

describe('distribute', () => {
  let store: ElementStore
  beforeEach(() => {
    store = makeStore()
  })

  it('distributes 3 elements horizontally with equal gaps', () => {
    // Anchors at x=0 (w=20) and x=200 (w=20). Span = 220, sizes = 60.
    // Gap = (220-60)/2 = 80.
    store.create({ id: 'a', type: 'rect', x: 0, y: 0, width: 20, height: 20 })
    store.create({ id: 'b', type: 'rect', x: 100, y: 0, width: 20, height: 20 })
    store.create({ id: 'c', type: 'rect', x: 200, y: 0, width: 20, height: 20 })
    distribute(store, new Set(['a', 'b', 'c']), 'horizontal')
    // b.x = a.right(20) + 80 = 100. (Already there → 0 moves.)
    expect(store.get('b')!.x).toBe(100)
    // a + c are anchors; positions unchanged.
    expect(store.get('a')!.x).toBe(0)
    expect(store.get('c')!.x).toBe(200)
  })

  it('moves the middle element to enforce equal gaps when off', () => {
    // a at 0, b at 50 (off-centre), c at 200.
    // Span = 220, sizes = 60, gap = 80. b.x should become 100.
    store.create({ id: 'a', type: 'rect', x: 0, y: 0, width: 20, height: 20 })
    store.create({ id: 'b', type: 'rect', x: 50, y: 0, width: 20, height: 20 })
    store.create({ id: 'c', type: 'rect', x: 200, y: 0, width: 20, height: 20 })
    distribute(store, new Set(['a', 'b', 'c']), 'horizontal')
    expect(store.get('b')!.x).toBe(100)
  })

  it('distributes vertically the same way', () => {
    store.create({ id: 'a', type: 'rect', x: 0, y: 0, width: 20, height: 20 })
    store.create({ id: 'b', type: 'rect', x: 0, y: 50, width: 20, height: 20 })
    store.create({ id: 'c', type: 'rect', x: 0, y: 200, width: 20, height: 20 })
    distribute(store, new Set(['a', 'b', 'c']), 'vertical')
    expect(store.get('b')!.y).toBe(100)
    expect(store.get('a')!.y).toBe(0)
    expect(store.get('c')!.y).toBe(200)
  })

  it('returns 0 for fewer than 3 unlocked elements', () => {
    store.create({ id: 'a', type: 'rect', x: 0, y: 0, width: 20, height: 20 })
    store.create({ id: 'b', type: 'rect', x: 100, y: 0, width: 20, height: 20 })
    expect(distribute(store, new Set(['a', 'b']), 'horizontal')).toBe(0)
  })

  it('skips locked elements (and counts only unlocked toward the 3-min)', () => {
    store.create({ id: 'a', type: 'rect', x: 0, y: 0, width: 20, height: 20 })
    store.create({
      id: 'b',
      type: 'rect',
      x: 50,
      y: 0,
      width: 20,
      height: 20,
      locked: true,
    })
    store.create({ id: 'c', type: 'rect', x: 200, y: 0, width: 20, height: 20 })
    // Only 2 unlocked → no-op.
    expect(distribute(store, new Set(['a', 'b', 'c']), 'horizontal')).toBe(0)
    expect(store.get('a')!.x).toBe(0)
    expect(store.get('b')!.x).toBe(50)
    expect(store.get('c')!.x).toBe(200)
  })
})
