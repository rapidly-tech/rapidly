/**
 * Collab provider — shared-memory transport pair tests (PR 17).
 *
 * These tests never touch a real ``PeerDataConnection``. They wire two
 * ``CollabRoom`` instances through a stubbed transport that pipes
 * ``send(msg)`` from one side into the other's ``onMessage`` handler.
 *
 * That lets us prove CRDT convergence + awareness + no-echo-loop
 * invariants without WebRTC, jsdom, or any network primitive.
 */

import { describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import type { CollabTransport } from './provider'
import { createCollabRoom, isCollabMessage } from './provider'

// ── Shared-memory transport pair ──

interface TransportPair {
  a: CollabTransport
  b: CollabTransport
}

/** Build an A↔B transport pair. ``a.send`` delivers to every handler
 *  registered on ``b`` and vice versa, synchronously — Yjs update
 *  delivery doesn't need async ordering for these tests. */
function makeTransportPair(idA = 'peer-a', idB = 'peer-b'): TransportPair {
  const handlersA: Array<(msg: { t: string; bytes: Uint8Array }) => void> = []
  const handlersB: Array<(msg: { t: string; bytes: Uint8Array }) => void> = []

  const a: CollabTransport = {
    peerId: idB, // from A's perspective the remote is B
    async send(msg) {
      for (const h of handlersB) h(msg)
    },
    onMessage(h) {
      handlersA.push(h)
      return () => {
        const i = handlersA.indexOf(h)
        if (i >= 0) handlersA.splice(i, 1)
      }
    },
  }
  const b: CollabTransport = {
    peerId: idA,
    async send(msg) {
      for (const h of handlersA) h(msg)
    },
    onMessage(h) {
      handlersB.push(h)
      return () => {
        const i = handlersB.indexOf(h)
        if (i >= 0) handlersB.splice(i, 1)
      }
    },
  }
  return { a, b }
}

// Yjs updates propagate through the transport synchronously in this
// harness, but the provider uses ``void transport.send(...).catch(...)``
// which resolves on the microtask queue. Flushing lets assertions see
// the converged state.
async function flush(): Promise<void> {
  await new Promise((r) => setTimeout(r, 0))
  await new Promise((r) => setTimeout(r, 0))
}

// ── Tests ──

describe('isCollabMessage', () => {
  it('accepts the three protocol messages', () => {
    const bytes = new Uint8Array([1, 2, 3])
    expect(isCollabMessage({ t: 'y-sync-1', bytes })).toBe(true)
    expect(isCollabMessage({ t: 'y-sync-2', bytes })).toBe(true)
    expect(isCollabMessage({ t: 'y-awareness', bytes })).toBe(true)
  })

  it('rejects unknown types', () => {
    expect(isCollabMessage({ t: 'junk', bytes: new Uint8Array() })).toBe(false)
    expect(isCollabMessage(null)).toBe(false)
    expect(isCollabMessage({ t: 'y-sync-1' })).toBe(false)
  })
})

describe('createCollabRoom — two-peer convergence', () => {
  it('syncs an edit made before the peer joined', async () => {
    const roomA = createCollabRoom({ selfPeerId: 'a' })
    const roomB = createCollabRoom({ selfPeerId: 'b' })

    // A has edits; B is empty. Connect and check B catches up.
    roomA.doc.getText('t').insert(0, 'hello')

    const { a, b } = makeTransportPair('a', 'b')
    roomA.addPeer(a) // A sends sync-1; B replies sync-2
    roomB.addPeer(b)
    await flush()

    expect(roomB.doc.getText('t').toString()).toBe('hello')

    roomA.close()
    roomB.close()
  })

  it('propagates live edits in both directions', async () => {
    const roomA = createCollabRoom({ selfPeerId: 'a' })
    const roomB = createCollabRoom({ selfPeerId: 'b' })
    const { a, b } = makeTransportPair('a', 'b')
    roomA.addPeer(a)
    roomB.addPeer(b)
    await flush()

    roomA.doc.getText('t').insert(0, 'A')
    await flush()
    expect(roomB.doc.getText('t').toString()).toBe('A')

    roomB.doc.getText('t').insert(1, 'B')
    await flush()
    expect(roomA.doc.getText('t').toString()).toBe('AB')

    roomA.close()
    roomB.close()
  })

  it('converges on concurrent edits (CRDT property)', async () => {
    // Yjs's correctness guarantee — two divergent edits applied in
    // either order must produce the same merged state.
    const roomA = createCollabRoom({ selfPeerId: 'a' })
    const roomB = createCollabRoom({ selfPeerId: 'b' })
    const { a, b } = makeTransportPair('a', 'b')
    roomA.addPeer(a)
    roomB.addPeer(b)
    await flush()

    // Both rooms edit position 0 "simultaneously" — each insert runs
    // against the other room's pre-edit state, exactly the scenario
    // y-webrtc peers hit on slow networks.
    roomA.doc.getText('t').insert(0, 'A')
    roomB.doc.getText('t').insert(0, 'B')
    await flush()

    expect(roomA.doc.getText('t').toString()).toBe(
      roomB.doc.getText('t').toString(),
    )
    expect(roomA.doc.getText('t').toString().length).toBe(2)

    roomA.close()
    roomB.close()
  })

  it('does not rebroadcast remote updates (no echo loop)', async () => {
    // If remote-origin updates were rebroadcast, a 3-peer ring would
    // blow up exponentially. We assert on a proxy: the number of
    // outbound messages from A after one of B's inserts must be zero.
    const roomA = createCollabRoom({ selfPeerId: 'a' })
    const roomB = createCollabRoom({ selfPeerId: 'b' })
    const { a, b } = makeTransportPair('a', 'b')

    let aSendCount = 0
    const wrappedA: CollabTransport = {
      peerId: a.peerId,
      async send(msg) {
        aSendCount += 1
        await a.send(msg)
      },
      onMessage: a.onMessage.bind(a),
    }

    roomA.addPeer(wrappedA)
    roomB.addPeer(b)
    await flush()
    const baseline = aSendCount

    roomB.doc.getText('t').insert(0, 'from-b')
    await flush()

    // A received sync-2 from B. A must NOT emit anything in response.
    expect(aSendCount).toBe(baseline)
    expect(roomA.doc.getText('t').toString()).toBe('from-b')

    roomA.close()
    roomB.close()
  })
})

describe('createCollabRoom — awareness (presence)', () => {
  it('propagates awareness state between peers', async () => {
    const roomA = createCollabRoom({ selfPeerId: 'a' })
    const roomB = createCollabRoom({ selfPeerId: 'b' })
    const { a, b } = makeTransportPair('a', 'b')
    roomA.addPeer(a)
    roomB.addPeer(b)
    await flush()

    roomA.awareness.setLocalState({ name: 'Alice', cursor: 5 })
    await flush()

    // Look up the entry corresponding to A's clientID in B's map.
    const entry = roomB.awareness.getStates().get(roomA.awareness.clientID)
    expect(entry).toEqual({ name: 'Alice', cursor: 5 })

    roomA.close()
    roomB.close()
  })
})

describe('createCollabRoom — peer lifecycle', () => {
  it('removePeer stops delivering updates to that peer', async () => {
    const roomA = createCollabRoom({ selfPeerId: 'a' })
    const roomB = createCollabRoom({ selfPeerId: 'b' })
    const { a, b } = makeTransportPair('a', 'b')
    roomA.addPeer(a)
    roomB.addPeer(b)
    await flush()

    roomA.removePeer(a.peerId)
    roomA.doc.getText('t').insert(0, 'never-seen')
    await flush()

    expect(roomB.doc.getText('t').toString()).toBe('')

    roomA.close()
    roomB.close()
  })

  it('close stops broadcasting', async () => {
    const roomA = createCollabRoom({ selfPeerId: 'a' })
    const roomB = createCollabRoom({ selfPeerId: 'b' })
    const { a, b } = makeTransportPair('a', 'b')
    roomA.addPeer(a)
    roomB.addPeer(b)
    await flush()

    roomA.close()
    roomA.doc.getText('t').insert(0, 'silent')
    await flush()

    expect(roomB.doc.getText('t').toString()).toBe('')

    roomB.close()
  })

  it('addPeer is idempotent — re-adding replaces the handler', async () => {
    const roomA = createCollabRoom({ selfPeerId: 'a' })
    const roomB = createCollabRoom({ selfPeerId: 'b' })
    const { a, b } = makeTransportPair('a', 'b')
    roomA.addPeer(a)
    roomB.addPeer(b)
    roomA.addPeer(a) // should not throw or double-subscribe
    await flush()

    roomA.doc.getText('t').insert(0, 'once')
    await flush()
    // Text landed exactly once on B — not doubled up.
    expect(roomB.doc.getText('t').toString()).toBe('once')

    roomA.close()
    roomB.close()
  })
})

describe('createCollabRoom — Y.Map and Y.Array shapes', () => {
  it('syncs Y.Map edits', async () => {
    const doc = new Y.Doc()
    const roomA = createCollabRoom({ selfPeerId: 'a', doc })
    const roomB = createCollabRoom({ selfPeerId: 'b' })
    const { a, b } = makeTransportPair('a', 'b')
    roomA.addPeer(a)
    roomB.addPeer(b)
    await flush()

    doc.getMap('m').set('key', 'value')
    await flush()

    expect(roomB.doc.getMap('m').get('key')).toBe('value')
    roomA.close()
    roomB.close()
  })

  it('syncs Y.Array pushes (canvas stroke shape)', async () => {
    const roomA = createCollabRoom({ selfPeerId: 'a' })
    const roomB = createCollabRoom({ selfPeerId: 'b' })
    const { a, b } = makeTransportPair('a', 'b')
    roomA.addPeer(a)
    roomB.addPeer(b)
    await flush()

    roomA.doc.getArray('strokes').push([{ x: 1, y: 2 }])
    await flush()

    expect(roomB.doc.getArray('strokes').toArray()).toEqual([{ x: 1, y: 2 }])
    roomA.close()
    roomB.close()
  })
})
