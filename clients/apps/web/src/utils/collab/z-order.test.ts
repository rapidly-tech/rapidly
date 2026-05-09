import { describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import { createElementStore } from './element-store'
import {
  bringForward,
  bringToFront,
  reorderedIds,
  sendBackward,
  sendToBack,
} from './z-order'

describe('reorderedIds (pure)', () => {
  const order = ['a', 'b', 'c', 'd', 'e']

  it('bringToFront moves selected to the end, preserving selected inner order', () => {
    expect(reorderedIds(order, new Set(['a', 'c']), 'front')).toEqual([
      'b',
      'd',
      'e',
      'a',
      'c',
    ])
  })

  it('sendToBack moves selected to the beginning', () => {
    expect(reorderedIds(order, new Set(['b', 'd']), 'back')).toEqual([
      'b',
      'd',
      'a',
      'c',
      'e',
    ])
  })

  it('bringForward swaps each selected with the next non-selected above', () => {
    // a[sel] b c → b a c
    expect(reorderedIds(['a', 'b', 'c'], new Set(['a']), 'forward')).toEqual([
      'b',
      'a',
      'c',
    ])
  })

  it('bringForward keeps selected together when stacked — moves the whole group up by one', () => {
    // a[sel] b[sel] c d → c a b d (group leapfrogs c)
    // But our algorithm swaps one at a time; the visible effect is:
    // walking high→low, b swaps with c → a c b d → stop at a.
    // Wait, a is still selected but above it is c which is unselected.
    // Next pass: no — we do single pass. Let me trace:
    //   i=2 (c): not selected, skip
    //   i=1 (b): selected, next is (c, unsel) → swap → [a, c, b, d]
    //   i=0 (a): selected, next is (c, unsel) → swap → [c, a, b, d]
    // So the group (a, b) moved above c together.
    expect(
      reorderedIds(['a', 'b', 'c', 'd'], new Set(['a', 'b']), 'forward'),
    ).toEqual(['c', 'a', 'b', 'd'])
  })

  it('bringForward is a no-op when selected is already at the top', () => {
    expect(reorderedIds(order, new Set(['e']), 'forward')).toEqual(order)
  })

  it('sendBackward moves selected one step down', () => {
    // a b[sel] c → b a c  (wait: symmetric walk low→high means
    //   i=1 (b): selected, prev (a) unsel → swap → a↔b → [b, a, c])
    expect(reorderedIds(['a', 'b', 'c'], new Set(['b']), 'backward')).toEqual([
      'b',
      'a',
      'c',
    ])
  })

  it('sendBackward is a no-op when selected is already at the bottom', () => {
    expect(reorderedIds(order, new Set(['a']), 'backward')).toEqual(order)
  })

  it('empty selection → order unchanged', () => {
    expect(reorderedIds(order, new Set(), 'front')).toEqual(order)
    expect(reorderedIds(order, new Set(), 'forward')).toEqual(order)
  })
})

describe('z-order store ops', () => {
  it('bringToFront renumbers zIndex contiguously with selected at top', () => {
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
    const c = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      roundness: 0,
    })
    bringToFront(store, new Set([a]))
    const ordered = store.list().map((el) => el.id)
    expect(ordered).toEqual([b, c, a])
    // Contiguous 0..N-1.
    expect(store.list().map((el) => el.zIndex)).toEqual([0, 1, 2])
  })

  it('sendToBack renumbers with selected at bottom', () => {
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
    const c = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      roundness: 0,
    })
    sendToBack(store, new Set([c]))
    expect(store.list().map((el) => el.id)).toEqual([c, a, b])
  })

  it('bringForward / sendBackward step one at a time', () => {
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
    const c = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      roundness: 0,
    })
    bringForward(store, new Set([a]))
    expect(store.list().map((el) => el.id)).toEqual([b, a, c])
    sendBackward(store, new Set([a]))
    expect(store.list().map((el) => el.id)).toEqual([a, b, c])
  })

  it('empty selection is a no-op — no store writes', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      roundness: 0,
    })
    let updates = 0
    doc.on('update', () => {
      updates++
    })
    bringToFront(store, new Set())
    sendToBack(store, new Set())
    bringForward(store, new Set())
    sendBackward(store, new Set())
    expect(updates).toBe(0)
  })
})
