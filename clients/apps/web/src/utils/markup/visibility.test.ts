import { describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import { createElementStore } from './element-store'
import type { CollabElement } from './elements'
import { isHidden, setHidden, toggleHidden } from './visibility'

const baseRect = {
  type: 'rect' as const,
  x: 0,
  y: 0,
  width: 10,
  height: 10,
  roundness: 0,
}

describe('setHidden', () => {
  it('marks every id in the selection hidden', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create(baseRect)
    const b = store.create(baseRect)
    setHidden(store, new Set([a, b]), true)
    expect(store.get(a)?.hidden).toBe(true)
    expect(store.get(b)?.hidden).toBe(true)
  })

  it('clears the flag when given hidden=false', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create({ ...baseRect, hidden: true })
    setHidden(store, new Set([id]), false)
    expect(store.get(id)?.hidden).toBeUndefined()
  })

  it('is a no-op for an empty selection', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect)
    setHidden(store, new Set(), true)
    expect(store.get(id)?.hidden).toBeUndefined()
  })

  it('skips ids that no longer resolve in the store', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create(baseRect)
    expect(() => setHidden(store, new Set([a, 'ghost']), true)).not.toThrow()
    expect(store.get(a)?.hidden).toBe(true)
  })
})

describe('toggleHidden', () => {
  it('hides everything when all are visible', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create(baseRect)
    const b = store.create(baseRect)
    toggleHidden(store, new Set([a, b]))
    expect(store.get(a)?.hidden).toBe(true)
    expect(store.get(b)?.hidden).toBe(true)
  })

  it('shows everything when all are hidden', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.create({ ...baseRect, hidden: true })
    const b = store.create({ ...baseRect, hidden: true })
    toggleHidden(store, new Set([a, b]))
    expect(store.get(a)?.hidden).toBeUndefined()
    expect(store.get(b)?.hidden).toBeUndefined()
  })

  it('hides everything when the set is mixed (next toggle flips all back)', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const visible = store.create(baseRect)
    const hidden = store.create({ ...baseRect, hidden: true })
    toggleHidden(store, new Set([visible, hidden]))
    expect(store.get(visible)?.hidden).toBe(true)
    expect(store.get(hidden)?.hidden).toBe(true)
  })

  it('is a no-op for an empty selection', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const id = store.create(baseRect)
    toggleHidden(store, new Set())
    expect(store.get(id)?.hidden).toBeUndefined()
  })
})

describe('isHidden', () => {
  it('returns true only for hidden:true (undefined and false are both visible)', () => {
    expect(
      isHidden({
        ...baseRect,
        id: 'a',
        hidden: true,
      } as unknown as CollabElement),
    ).toBe(true)
    expect(
      isHidden({
        ...baseRect,
        id: 'b',
        hidden: false,
      } as unknown as CollabElement),
    ).toBe(false)
    expect(isHidden({ ...baseRect, id: 'c' } as unknown as CollabElement)).toBe(
      false,
    )
  })
})
