import { describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import { createElementStore, type ElementStore } from './element-store'
import { createUndoManager } from './undo'

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

describe('createUndoManager', () => {
  it('starts with empty stacks', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const undo = createUndoManager(store)
    expect(undo.canUndo()).toBe(false)
    expect(undo.canRedo()).toBe(false)
    expect(undo.undo()).toBe(false)
    expect(undo.redo()).toBe(false)
    undo.dispose()
  })

  it('undoes a create; redo re-creates', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const undo = createUndoManager(store)
    const a = rect(store)
    expect(store.has(a)).toBe(true)
    expect(undo.undo()).toBe(true)
    expect(store.has(a)).toBe(false)
    expect(undo.redo()).toBe(true)
    expect(store.has(a)).toBe(true)
    undo.dispose()
  })

  it('undoes an update; redo re-applies', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const undo = createUndoManager(store)
    const a = rect(store)
    store.update(a, { x: 500 })
    expect(store.get(a)!.x).toBe(500)
    undo.undo()
    expect(store.get(a)!.x).toBe(0)
    undo.redo()
    expect(store.get(a)!.x).toBe(500)
    undo.dispose()
  })

  it('undoes a delete; redo re-deletes', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const undo = createUndoManager(store)
    const a = rect(store)
    store.delete(a)
    expect(store.has(a)).toBe(false)
    undo.undo()
    expect(store.has(a)).toBe(true)
    undo.redo()
    expect(store.has(a)).toBe(false)
    undo.dispose()
  })

  it('a single updateMany is one undo step', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const undo = createUndoManager(store)
    const a = rect(store)
    const b = rect(store)
    // Clear the stack from the two creates.
    undo.undo()
    undo.undo()
    expect(store.size).toBe(0)
    undo.redo()
    undo.redo()
    // Now a single updateMany should be one step.
    store.updateMany([
      { id: a, patch: { x: 100 } },
      { id: b, patch: { x: 100 } },
    ])
    undo.undo()
    expect(store.get(a)!.x).toBe(0)
    expect(store.get(b)!.x).toBe(0)
    undo.dispose()
  })

  it('ignores remote-origin transactions', () => {
    // Two docs via direct state-vector exchange — the "remote" side's
    // origin differs from ORIGIN_LOCAL so our manager must not track
    // its mutations.
    const local = new Y.Doc()
    const remote = new Y.Doc()
    const localStore = createElementStore(local)
    const remoteStore = createElementStore(remote)
    const undo = createUndoManager(localStore)

    // Remote creates.
    const rid = remoteStore.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      roundness: 0,
    })
    // Ship the remote edit over to local with a distinct origin.
    const update = Y.encodeStateAsUpdate(remote)
    Y.applyUpdate(local, update, 'remote-peer')
    expect(localStore.has(rid)).toBe(true)
    // Undo stack should still be empty — remote edits aren't tracked.
    expect(undo.canUndo()).toBe(false)
    undo.dispose()
  })

  it('subscribe fires on push and on undo', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const undo = createUndoManager(store)
    let calls = 0
    const off = undo.subscribe(() => {
      calls++
    })
    rect(store)
    const afterPush = calls
    expect(afterPush).toBeGreaterThan(0)
    undo.undo()
    expect(calls).toBeGreaterThan(afterPush)
    off()
    const beforeSilent = calls
    rect(store)
    expect(calls).toBe(beforeSilent)
    undo.dispose()
  })

  it('dispose stops listeners and prevents further events', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const undo = createUndoManager(store)
    let calls = 0
    undo.subscribe(() => {
      calls++
    })
    rect(store)
    expect(calls).toBeGreaterThan(0)
    undo.dispose()
    const frozen = calls
    rect(store)
    // After dispose, no further events.
    expect(calls).toBe(frozen)
  })
})
