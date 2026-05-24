/**
 * Clear-canvas — pinned behaviour:
 *
 * - Deletes every element in one transaction.
 * - Locked elements ARE removed (deliberate action).
 * - Empty store is a no-op (returns 0).
 * - Bound arrow endpoints / group ids in surviving elements would be
 *   moot — there are no survivors.
 */

import { describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import { clearCanvas } from './clear-canvas'
import { createElementStore } from './element-store'

describe('clearCanvas', () => {
  it('removes every element', () => {
    const store = createElementStore(new Y.Doc())
    store.create({ type: 'rect', x: 0, y: 0, width: 10, height: 10 })
    store.create({ type: 'rect', x: 20, y: 20, width: 10, height: 10 })
    const removed = clearCanvas(store)
    expect(removed).toBe(2)
    expect(store.size).toBe(0)
  })

  it('removes locked elements too (deliberate action)', () => {
    const store = createElementStore(new Y.Doc())
    store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      locked: true,
    })
    expect(clearCanvas(store)).toBe(1)
    expect(store.size).toBe(0)
  })

  it('is a no-op on an empty store', () => {
    const store = createElementStore(new Y.Doc())
    expect(clearCanvas(store)).toBe(0)
  })

  it('runs in a single Yjs transaction', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    store.create({ type: 'rect', x: 0, y: 0, width: 10, height: 10 })
    store.create({ type: 'rect', x: 20, y: 20, width: 10, height: 10 })
    let txCount = 0
    doc.on('afterTransaction', () => {
      txCount++
    })
    clearCanvas(store)
    expect(txCount).toBe(1)
  })
})
