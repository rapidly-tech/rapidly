import { beforeEach, describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import {
  _resetClipboard,
  copy,
  cut,
  duplicate,
  getClipboard,
  paste,
  serialiseSelection,
} from './clipboard'
import { createElementStore, type ElementStore } from './element-store'
import { group } from './groups'

function rect(
  store: ElementStore,
  overrides: Record<string, unknown> = {},
): string {
  return store.create({
    type: 'rect',
    x: 0,
    y: 0,
    width: 10,
    height: 10,
    roundness: 0,
    ...overrides,
  })
}

describe('serialiseSelection', () => {
  it('returns null for an empty selection', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    expect(serialiseSelection(store, new Set())).toBeNull()
  })

  it('captures selected elements in paint order (low-z first)', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store) // z=0
    const b = rect(store) // z=1
    const payload = serialiseSelection(store, new Set([b, a]))!
    expect(payload.elements.map((el) => el.id)).toEqual([a, b])
  })

  it('captures by value — later edits do not leak into the snapshot', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store, { x: 100 })
    const payload = serialiseSelection(store, new Set([a]))!
    store.update(a, { x: 500 })
    expect(payload.elements[0].x).toBe(100)
  })
})

describe('copy / paste round-trip', () => {
  beforeEach(() => _resetClipboard())

  it('paste creates new ids, never reuses originals', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    copy(store, new Set([a]))
    const newIds = paste(store, getClipboard())
    expect(newIds).toHaveLength(1)
    expect(newIds[0]).not.toBe(a)
    expect(store.size).toBe(2)
  })

  it('paste offsets by a small delta so copies do not stack exactly', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store, { x: 100, y: 200 })
    copy(store, new Set([a]))
    const [newId] = paste(store, getClipboard())
    const pasted = store.get(newId)!
    expect(pasted.x).toBe(116)
    expect(pasted.y).toBe(216)
  })

  it('paste lands on top of the existing stack', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    rect(store) // b, ends at z=1
    rect(store) // c, z=2
    copy(store, new Set([a]))
    const [newId] = paste(store, getClipboard())
    expect(store.get(newId)!.zIndex).toBe(3)
  })

  it('paste preserves the relative z-order of the copied batch', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store) // z=0
    const b = rect(store) // z=1
    copy(store, new Set([a, b]))
    const newIds = paste(store, getClipboard())
    const pastedA = store.get(newIds[0])!
    const pastedB = store.get(newIds[1])!
    expect(pastedA.zIndex).toBeLessThan(pastedB.zIndex)
  })

  it('paste with zero elements is a no-op', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    expect(paste(store, null)).toEqual([])
    expect(paste(store, { magic: 'rapidly-collab-v1', elements: [] })).toEqual(
      [],
    )
  })
})

describe('group id rewriting on paste', () => {
  beforeEach(() => _resetClipboard())

  it('pasted grouped elements form a new group, still bound together', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    const b = rect(store)
    const gid = group(store, new Set([a, b]))!
    copy(store, new Set([a, b]))
    const [pa, pb] = paste(store, getClipboard())
    const pastedA = store.get(pa)!
    const pastedB = store.get(pb)!
    expect(pastedA.groupIds).toHaveLength(1)
    expect(pastedB.groupIds).toHaveLength(1)
    expect(pastedA.groupIds[0]).toBe(pastedB.groupIds[0])
    expect(pastedA.groupIds[0]).not.toBe(gid)
  })

  it('distinct groups in the copy remain distinct after paste', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    const b = rect(store)
    const c = rect(store)
    const d = rect(store)
    group(store, new Set([a, b]))
    group(store, new Set([c, d]))
    copy(store, new Set([a, b, c, d]))
    const newIds = paste(store, getClipboard())
    const gA = store.get(newIds[0])!.groupIds[0]
    const gB = store.get(newIds[1])!.groupIds[0]
    const gC = store.get(newIds[2])!.groupIds[0]
    const gD = store.get(newIds[3])!.groupIds[0]
    expect(gA).toBe(gB)
    expect(gC).toBe(gD)
    expect(gA).not.toBe(gC)
  })

  it('group ids of uncopied siblings are stripped', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    const b = rect(store)
    group(store, new Set([a, b]))
    // Copy only a — b stays in the source doc but is not in the clipboard.
    copy(store, new Set([a]))
    const [pa] = paste(store, getClipboard())
    // The pasted a still gets a fresh group id (just itself), so
    // subsequent Cmd+G joins make sense. But since a was the lone
    // member copied, its group remap contains one new id.
    expect(store.get(pa)!.groupIds).toHaveLength(1)
  })
})

describe('arrow binding rewriting on paste', () => {
  beforeEach(() => _resetClipboard())

  it('preserves bindings when both endpoints are in the copy set', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const boxA = rect(store)
    const boxB = rect(store)
    const arrow = store.create({
      type: 'arrow',
      x: 0,
      y: 0,
      width: 100,
      height: 0,
      points: [0, 0, 100, 0],
      startBinding: { elementId: boxA, focus: 0, gap: 4 },
      endBinding: { elementId: boxB, focus: 0, gap: 4 },
    })
    copy(store, new Set([boxA, boxB, arrow]))
    const newIds = paste(store, getClipboard())
    const pastedArrow = store.list().find((el) => el.id === newIds[2])!
    // Arrow references its own pasted endpoints, not the originals.
    expect(
      (pastedArrow as { startBinding?: { elementId: string } }).startBinding
        ?.elementId,
    ).toBe(newIds[0])
    expect(
      (pastedArrow as { endBinding?: { elementId: string } }).endBinding
        ?.elementId,
    ).toBe(newIds[1])
  })

  it('drops bindings that would dangle to a non-copied target', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const boxA = rect(store)
    const boxB = rect(store)
    const arrow = store.create({
      type: 'arrow',
      x: 0,
      y: 0,
      width: 100,
      height: 0,
      points: [0, 0, 100, 0],
      startBinding: { elementId: boxA, focus: 0, gap: 4 },
      endBinding: { elementId: boxB, focus: 0, gap: 4 },
    })
    // Copy only the arrow + boxA; boxB is not in the set.
    copy(store, new Set([boxA, arrow]))
    const newIds = paste(store, getClipboard())
    const pastedArrow = store.list().find((el) => el.id === newIds[1])!
    expect(
      (pastedArrow as { startBinding?: { elementId: string } }).startBinding
        ?.elementId,
    ).toBe(newIds[0])
    // Dangling end binding is dropped — arrow endpoint is free.
    expect((pastedArrow as { endBinding?: unknown }).endBinding).toBeUndefined()
  })
})

describe('cut / duplicate', () => {
  beforeEach(() => _resetClipboard())

  it('cut copies to the clipboard and removes the originals', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    cut(store, new Set([a]))
    expect(store.has(a)).toBe(false)
    // Pasting the cut gets them back with fresh ids.
    const [newId] = paste(store, getClipboard())
    expect(newId).not.toBe(a)
    expect(store.has(newId)).toBe(true)
  })

  it('duplicate produces a copy without touching the clipboard', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    // Seed the clipboard with something else first.
    copy(store, new Set([a]))
    const buffered = getClipboard()
    const newIds = duplicate(store, new Set([a]))
    expect(newIds).toHaveLength(1)
    // Clipboard reference unchanged.
    expect(getClipboard()).toBe(buffered)
  })

  it('duplicate with empty selection is a no-op', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    expect(duplicate(store, new Set())).toEqual([])
  })
})
