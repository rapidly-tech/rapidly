import { describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import { createElementStore, type ElementStore } from './element-store'
import {
  allLocked,
  filterUnlocked,
  isLocked,
  setLock,
  toggleLock,
} from './locks'

function rect(store: ElementStore): string {
  return store.create({
    type: 'rect',
    x: 0,
    y: 0,
    width: 10,
    height: 10,
    roundness: 0,
  })
}

describe('isLocked', () => {
  it('defaults to false for fresh elements', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    expect(isLocked(store.get(a)!)).toBe(false)
  })
})

describe('toggleLock', () => {
  it('flips each element individually when selection is mixed', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    const b = rect(store)
    setLock(store, new Set([a]), true)
    toggleLock(store, new Set([a, b]))
    expect(isLocked(store.get(a)!)).toBe(false)
    expect(isLocked(store.get(b)!)).toBe(true)
  })

  it('no-op on empty selection', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    expect(toggleLock(store, new Set())).toBe(false)
  })

  it('emits a single Yjs update per call', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    const b = rect(store)
    let updates = 0
    doc.on('update', () => {
      updates++
    })
    toggleLock(store, new Set([a, b]))
    expect(updates).toBe(1)
  })
})

describe('setLock', () => {
  it('forces all selected to the target state', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    const b = rect(store)
    setLock(store, new Set([a]), true)
    setLock(store, new Set([a, b]), true)
    expect(isLocked(store.get(a)!)).toBe(true)
    expect(isLocked(store.get(b)!)).toBe(true)
  })

  it('skips elements already in the target state — no write', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    setLock(store, new Set([a]), true)
    let updates = 0
    doc.on('update', () => {
      updates++
    })
    expect(setLock(store, new Set([a]), true)).toBe(false)
    expect(updates).toBe(0)
  })
})

describe('filterUnlocked', () => {
  it('drops locked ids, keeps unlocked ones', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    const b = rect(store)
    const c = rect(store)
    setLock(store, new Set([b]), true)
    const out = filterUnlocked(store, new Set([a, b, c]))
    expect(out.has(a)).toBe(true)
    expect(out.has(b)).toBe(false)
    expect(out.has(c)).toBe(true)
  })

  it('drops ids missing from the store', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    const out = filterUnlocked(store, new Set([a, 'ghost']))
    expect(out.has('ghost')).toBe(false)
    expect(out.has(a)).toBe(true)
  })
})

describe('allLocked', () => {
  it('true only when every element is locked and list is non-empty', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    const b = rect(store)
    setLock(store, new Set([a, b]), true)
    expect(allLocked([store.get(a)!, store.get(b)!])).toBe(true)
  })

  it('false if any element is unlocked', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    const b = rect(store)
    setLock(store, new Set([a]), true)
    expect(allLocked([store.get(a)!, store.get(b)!])).toBe(false)
  })

  it('false for an empty list', () => {
    expect(allLocked([])).toBe(false)
  })
})
