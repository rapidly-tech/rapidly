import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as Y from 'yjs'

import { createElementStore } from './element-store'
import {
  createPersistence,
  inMemoryStorage,
  PERSISTENCE_ORIGIN,
} from './persistence'

describe('createPersistence', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('writes a snapshot after a debounce window', async () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const storage = inMemoryStorage()
    const p = createPersistence({ doc, roomId: 'r', storage, debounceMs: 50 })

    store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      roundness: 0,
    })
    // Before the debounce elapses, storage is still empty.
    expect(await storage.get('r')).toBeNull()

    await vi.advanceTimersByTimeAsync(60)
    // Flush any microtasks the setTimeout produced.
    await Promise.resolve()

    const saved = await storage.get('r')
    expect(saved).not.toBeNull()
    expect(saved!.byteLength).toBeGreaterThan(0)
    p.dispose()
  })

  it('coalesces rapid edits into one write', async () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const storage = inMemoryStorage()
    const put = vi.spyOn(storage, 'put')
    const p = createPersistence({ doc, roomId: 'r', storage, debounceMs: 50 })

    for (let i = 0; i < 10; i++) {
      store.create({
        type: 'rect',
        x: i,
        y: 0,
        width: 10,
        height: 10,
        roundness: 0,
      })
    }

    await vi.advanceTimersByTimeAsync(60)
    await Promise.resolve()
    expect(put).toHaveBeenCalledTimes(1)
    p.dispose()
  })

  it('force-saves immediately on save()', async () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const storage = inMemoryStorage()
    const p = createPersistence({
      doc,
      roomId: 'r',
      storage,
      debounceMs: 1000,
    })

    store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      roundness: 0,
    })
    // Don't wait the 1000 ms — force-save.
    await p.save()
    expect(await storage.get('r')).not.toBeNull()
    p.dispose()
  })

  it('dispose cancels the pending save and stops listening', async () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const storage = inMemoryStorage()
    const put = vi.spyOn(storage, 'put')
    const p = createPersistence({ doc, roomId: 'r', storage, debounceMs: 50 })

    store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      roundness: 0,
    })
    p.dispose()
    await vi.advanceTimersByTimeAsync(100)
    await Promise.resolve()
    expect(put).not.toHaveBeenCalled()

    // Subsequent edits after dispose are ignored.
    store.create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      roundness: 0,
    })
    await vi.advanceTimersByTimeAsync(100)
    await Promise.resolve()
    expect(put).not.toHaveBeenCalled()
  })

  it('load hydrates a fresh doc from stored bytes', async () => {
    // First doc: create an element, save.
    const storage = inMemoryStorage()
    const doc1 = new Y.Doc()
    const store1 = createElementStore(doc1)
    const p1 = createPersistence({
      doc: doc1,
      roomId: 'r',
      storage,
      debounceMs: 50,
    })
    store1.create({
      type: 'rect',
      x: 42,
      y: 7,
      width: 10,
      height: 10,
      roundness: 0,
    })
    await p1.save()
    p1.dispose()

    // Second doc: load from the same storage and verify the element
    // shows up.
    const doc2 = new Y.Doc()
    const store2 = createElementStore(doc2)
    const p2 = createPersistence({ doc: doc2, roomId: 'r', storage })
    const loaded = await p2.load()
    expect(loaded).toBe(true)
    const el = store2.list()[0]
    expect(el).toBeDefined()
    expect(el.x).toBe(42)
    expect(el.y).toBe(7)
    p2.dispose()
  })

  it('load returns false when no entry exists', async () => {
    const doc = new Y.Doc()
    const storage = inMemoryStorage()
    const p = createPersistence({ doc, roomId: 'never-written', storage })
    expect(await p.load()).toBe(false)
    p.dispose()
  })

  it('different rooms do not collide', async () => {
    const storage = inMemoryStorage()
    const a = new Y.Doc()
    const b = new Y.Doc()
    createElementStore(a).create({
      type: 'rect',
      x: 1,
      y: 1,
      width: 10,
      height: 10,
      roundness: 0,
    })
    createElementStore(b).create({
      type: 'rect',
      x: 2,
      y: 2,
      width: 10,
      height: 10,
      roundness: 0,
    })
    const pa = createPersistence({ doc: a, roomId: 'room-a', storage })
    const pb = createPersistence({ doc: b, roomId: 'room-b', storage })
    await pa.save()
    await pb.save()

    expect(await storage.get('room-a')).not.toBeNull()
    expect(await storage.get('room-b')).not.toBeNull()

    const reloadA = new Y.Doc()
    const storeA = createElementStore(reloadA)
    const pra = createPersistence({ doc: reloadA, roomId: 'room-a', storage })
    await pra.load()
    expect(storeA.list()[0].x).toBe(1)

    pa.dispose()
    pb.dispose()
    pra.dispose()
  })

  it('hydration uses the PERSISTENCE_ORIGIN on the transaction', async () => {
    const storage = inMemoryStorage()
    const doc1 = new Y.Doc()
    createElementStore(doc1).create({
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      roundness: 0,
    })
    const p1 = createPersistence({ doc: doc1, roomId: 'r', storage })
    await p1.save()
    p1.dispose()

    const doc2 = new Y.Doc()
    const origins: unknown[] = []
    doc2.on('update', (_update: Uint8Array, origin: unknown) => {
      origins.push(origin)
    })
    const p2 = createPersistence({ doc: doc2, roomId: 'r', storage })
    await p2.load()
    expect(origins).toContain(PERSISTENCE_ORIGIN)
    p2.dispose()
  })
})
