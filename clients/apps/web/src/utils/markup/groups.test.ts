import { describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import { createElementStore } from './element-store'
import {
  computeGroupPatches,
  computeUngroupPatches,
  expandToGroups,
  group,
  innermostGroupId,
  outermostGroupId,
  ungroup,
} from './groups'

function rect(store: ReturnType<typeof createElementStore>): string {
  return store.create({
    type: 'rect',
    x: 0,
    y: 0,
    width: 10,
    height: 10,
    roundness: 0,
  })
}

describe('computeGroupPatches (pure)', () => {
  it('wraps two elements in a new innermost group', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.get(rect(store))!
    const b = store.get(rect(store))!
    const { groupId, patches } = computeGroupPatches([a, b], 'G1')
    expect(groupId).toBe('G1')
    expect(patches).toHaveLength(2)
    expect(patches[0].patch.groupIds).toEqual(['G1'])
    expect(patches[1].patch.groupIds).toEqual(['G1'])
  })

  it('appends the new group id to existing groupIds (outermost-last)', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.get(rect(store))!
    const b = store.get(rect(store))!
    store.updateMany([
      { id: a.id, patch: { groupIds: ['INNER'] } },
      { id: b.id, patch: { groupIds: ['INNER'] } },
    ])
    const fresh = [store.get(a.id)!, store.get(b.id)!]
    const { patches } = computeGroupPatches(fresh, 'OUTER')
    // New group wraps the existing one → appended at the outer end.
    expect(patches[0].patch.groupIds).toEqual(['INNER', 'OUTER'])
    expect(patches[1].patch.groupIds).toEqual(['INNER', 'OUTER'])
  })

  it('returns empty patches for a single-element selection', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.get(rect(store))!
    const { groupId, patches } = computeGroupPatches([a], 'G1')
    expect(groupId).toBeNull()
    expect(patches).toEqual([])
  })

  it('returns empty patches for no elements', () => {
    const { groupId, patches } = computeGroupPatches([], 'G1')
    expect(groupId).toBeNull()
    expect(patches).toEqual([])
  })
})

describe('computeUngroupPatches (pure)', () => {
  it('strips the outermost group from every grouped element', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    const b = rect(store)
    store.updateMany([
      { id: a, patch: { groupIds: ['G_INNER', 'G_OUTER'] } },
      { id: b, patch: { groupIds: ['G_INNER', 'G_OUTER'] } },
    ])
    const patches = computeUngroupPatches([store.get(a)!, store.get(b)!])
    expect(patches[0].patch.groupIds).toEqual(['G_INNER'])
    expect(patches[1].patch.groupIds).toEqual(['G_INNER'])
  })

  it('skips elements that are not in any group', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.get(rect(store))!
    const patches = computeUngroupPatches([a])
    expect(patches).toEqual([])
  })
})

describe('group / ungroup round-trip', () => {
  it('group writes identical groupIds to every selected element', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    const b = rect(store)
    const c = rect(store)
    const gid = group(store, new Set([a, b, c]))
    expect(gid).not.toBeNull()
    expect(store.get(a)!.groupIds).toEqual([gid])
    expect(store.get(b)!.groupIds).toEqual([gid])
    expect(store.get(c)!.groupIds).toEqual([gid])
  })

  it('ungroup reverses the innermost grouping', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    const b = rect(store)
    group(store, new Set([a, b]))
    ungroup(store, new Set([a, b]))
    expect(store.get(a)!.groupIds).toEqual([])
    expect(store.get(b)!.groupIds).toEqual([])
  })

  it('ungroup only peels one layer per call — nested groups survive', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    const b = rect(store)
    const inner = group(store, new Set([a, b]))!
    const outer = group(store, new Set([a, b]))!
    // innermost-first — the first call is deepest, the second wraps it.
    expect(store.get(a)!.groupIds).toEqual([inner, outer])
    ungroup(store, new Set([a, b]))
    expect(store.get(a)!.groupIds).toEqual([inner])
  })

  it('group is a no-op for a single element', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    let updates = 0
    doc.on('update', () => {
      updates++
    })
    const gid = group(store, new Set([a]))
    expect(gid).toBeNull()
    expect(updates).toBe(0)
  })

  it('group emits a single Yjs update per call', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    const b = rect(store)
    const c = rect(store)
    let updates = 0
    doc.on('update', () => {
      updates++
    })
    group(store, new Set([a, b, c]))
    expect(updates).toBe(1)
  })
})

describe('expandToGroups', () => {
  it('returns seeds untouched when no element is grouped', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    const b = rect(store)
    expect(expandToGroups(store, new Set([a]))).toEqual(new Set([a]))
    expect(expandToGroups(store, new Set([a, b]))).toEqual(new Set([a, b]))
  })

  it('expands one group member to the whole group', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    const b = rect(store)
    const c = rect(store) // not in group
    group(store, new Set([a, b]))
    expect(expandToGroups(store, new Set([a]))).toEqual(new Set([a, b]))
    expect(expandToGroups(store, new Set([c]))).toEqual(new Set([c]))
  })

  it('nested groups expand to the outermost', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    const b = rect(store)
    const c = rect(store)
    group(store, new Set([a, b])) // inner
    group(store, new Set([a, b, c])) // outer
    expect(expandToGroups(store, new Set([a]))).toEqual(new Set([a, b, c]))
  })

  it('empty seeds returns an empty set', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    rect(store)
    expect(expandToGroups(store, new Set())).toEqual(new Set())
  })

  it('is idempotent', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    const b = rect(store)
    group(store, new Set([a, b]))
    const once = expandToGroups(store, new Set([a]))
    const twice = expandToGroups(store, once)
    expect(twice).toEqual(once)
  })
})

describe('helpers', () => {
  it('innermostGroupId / outermostGroupId distinguish the chain ends', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    store.update(a, { groupIds: ['G_INNER', 'G_OUTER'] })
    const el = store.get(a)!
    expect(innermostGroupId(el)).toBe('G_INNER')
    expect(outermostGroupId(el)).toBe('G_OUTER')
  })

  it('return null when ungrouped', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = store.get(rect(store))!
    expect(innermostGroupId(a)).toBeNull()
    expect(outermostGroupId(a)).toBeNull()
  })
})
