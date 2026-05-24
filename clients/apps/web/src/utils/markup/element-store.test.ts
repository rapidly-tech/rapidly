import { describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import {
  createElementStore,
  ELEMENTS_KEY,
  ElementStore,
  ORIGIN_LOCAL,
} from './element-store'
import {
  isCollabElement,
  paintOrder,
  type CollabElement,
  type RectElement,
} from './elements'

function newStore(): { doc: Y.Doc; store: ElementStore } {
  const doc = new Y.Doc()
  const store = createElementStore(doc)
  return { doc, store }
}

describe('ElementStore', () => {
  it('creates a rect with defaults and an auto-assigned id', () => {
    const { store } = newStore()
    const id = store.create({
      type: 'rect',
      x: 10,
      y: 20,
      width: 100,
      height: 50,
      roundness: 0,
    })

    expect(id).toMatch(/^[A-Za-z0-9_-]{12}$/)
    const el = store.get(id)
    expect(el).not.toBeNull()
    expect(el?.type).toBe('rect')
    expect((el as RectElement).roundness).toBe(0)
    expect(el?.x).toBe(10)
    expect(el?.width).toBe(100)
    expect(el?.zIndex).toBe(0)
    expect(el?.version).toBe(1)
    expect(el?.locked).toBe(false)
    expect(el?.groupIds).toEqual([])
  })

  it('assigns monotonically increasing zIndex on create', () => {
    const { store } = newStore()
    const a = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      roundness: 0,
    })
    const b = store.create({
      type: 'ellipse',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
    })
    expect(store.get(a)?.zIndex).toBe(0)
    expect(store.get(b)?.zIndex).toBe(1)
  })

  it('list() returns elements sorted by (zIndex, id)', () => {
    const { store } = newStore()
    const top = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 1,
      height: 1,
      roundness: 0,
      zIndex: 5,
    })
    const bottom = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 1,
      height: 1,
      roundness: 0,
      zIndex: 0,
    })
    const order = store.list().map((e) => e.id)
    expect(order).toEqual([bottom, top])
  })

  it('update() bumps version', () => {
    const { store } = newStore()
    const id = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      roundness: 0,
    })
    store.update(id, { x: 99 })
    const after = store.get(id)
    expect(after?.x).toBe(99)
    expect(after?.version).toBe(2)
  })

  it('delete() is idempotent', () => {
    const { store } = newStore()
    const id = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      roundness: 0,
    })
    store.delete(id)
    store.delete(id) // second delete is a no-op
    expect(store.get(id)).toBeNull()
    expect(store.size).toBe(0)
  })

  it('tags every mutation with ORIGIN_LOCAL so UndoManager can scope', () => {
    const { doc, store } = newStore()
    const origins: unknown[] = []
    doc.on('update', (_update: Uint8Array, origin: unknown) => {
      origins.push(origin)
    })

    store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      roundness: 0,
    })
    expect(origins).toContain(ORIGIN_LOCAL)
  })

  it('updateMany batches into one transaction', () => {
    const { doc, store } = newStore()
    const a = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      roundness: 0,
    })
    const b = store.create({
      type: 'ellipse',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
    })

    let updateCount = 0
    doc.on('update', () => {
      updateCount++
    })

    store.updateMany([
      { id: a, patch: { x: 100 } },
      { id: b, patch: { x: 200 } },
    ])

    // One update event for the single transaction, not two.
    expect(updateCount).toBe(1)
    expect(store.get(a)?.x).toBe(100)
    expect(store.get(b)?.x).toBe(200)
  })

  it('rejects corrupt Y.Map entries on read', () => {
    const { doc, store } = newStore()
    const root = doc.getMap<Y.Map<unknown>>(ELEMENTS_KEY)
    const corrupt = new Y.Map<unknown>()
    corrupt.set('id', 'bad')
    corrupt.set('type', 'rect')
    // Missing every other required field.
    root.set('bad', corrupt)

    expect(store.get('bad')).toBeNull()
    // list() skips bad entries instead of throwing.
    expect(store.list()).toEqual([])
  })

  it('normaliseZOrder collapses duplicate/sparse zIndex to contiguous ints', () => {
    const { store } = newStore()
    const a = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 1,
      height: 1,
      roundness: 0,
      zIndex: 50,
    })
    const b = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 1,
      height: 1,
      roundness: 0,
      zIndex: 50,
    })
    const c = store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 1,
      height: 1,
      roundness: 0,
      zIndex: 1000,
    })

    store.normaliseZOrder()
    const zs = [a, b, c].map((id) => store.get(id)?.zIndex)
    // Contiguous 0, 1, 2 — order depends on id tiebreak for (a, b).
    expect(new Set(zs)).toEqual(new Set([0, 1, 2]))
  })
})

describe('isCollabElement', () => {
  it('accepts a well-formed rect', () => {
    const el: CollabElement = {
      id: 'abc',
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      angle: 0,
      zIndex: 0,
      groupIds: [],
      strokeColor: '#000',
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 2,
      strokeStyle: 'solid',
      roughness: 1,
      opacity: 100,
      seed: 1,
      version: 1,
      locked: false,
      roundness: 0,
    }
    expect(isCollabElement(el)).toBe(true)
  })

  it('rejects missing required fields', () => {
    expect(isCollabElement({ id: 'x', type: 'rect' })).toBe(false)
    expect(isCollabElement(null)).toBe(false)
    expect(isCollabElement('hello')).toBe(false)
  })

  it('rejects unknown element types', () => {
    const bad = {
      id: 'abc',
      type: 'spaceship',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      angle: 0,
      zIndex: 0,
      groupIds: [],
      strokeColor: '#000',
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 2,
      strokeStyle: 'solid',
      roughness: 1,
      opacity: 100,
      seed: 1,
      version: 1,
      locked: false,
    }
    expect(isCollabElement(bad)).toBe(false)
  })
})

describe('paintOrder', () => {
  it('orders by zIndex ascending', () => {
    const a = { zIndex: 1, id: 'a' } as CollabElement
    const b = { zIndex: 2, id: 'b' } as CollabElement
    expect(paintOrder(a, b)).toBeLessThan(0)
  })

  it('uses id as a tiebreak when zIndex is equal', () => {
    const a = { zIndex: 0, id: 'a' } as CollabElement
    const b = { zIndex: 0, id: 'b' } as CollabElement
    expect(paintOrder(a, b)).toBeLessThan(0)
    expect(paintOrder(b, a)).toBeGreaterThan(0)
  })
})
