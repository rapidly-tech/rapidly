/**
 * End-to-end verification that the provider compresses large payloads,
 * sets the ``z`` flag, survives the encrypt/decrypt round trip, and
 * delivers the original plaintext to the receiver.
 *
 * Transport pair + flush timing mirror ``provider.e2ee.test.ts`` so
 * microtask-heavy compression + decryption has enough cycles to settle
 * before assertions run.
 */

import { describe, expect, it } from 'vitest'

import { generateMasterKey, generateSalt } from '@/utils/crypto/master-key'

import { compressionAvailable } from './compression'
import {
  createCollabRoom,
  deriveCollabKeys,
  type CollabTransport,
  type CollabWireMessage,
} from './provider'

async function freshKeys() {
  const master = await generateMasterKey()
  const salt = generateSalt()
  return deriveCollabKeys(master, salt)
}

interface TransportPair {
  a: CollabTransport
  b: CollabTransport
  aToB: CollabWireMessage[]
  bToA: CollabWireMessage[]
}

function makeTransportPair(): TransportPair {
  const handlersA: Array<(msg: CollabWireMessage) => void> = []
  const handlersB: Array<(msg: CollabWireMessage) => void> = []
  const aToB: CollabWireMessage[] = []
  const bToA: CollabWireMessage[] = []
  const a: CollabTransport = {
    peerId: 'b',
    async send(msg) {
      aToB.push(msg)
      await Promise.resolve()
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
    peerId: 'a',
    async send(msg) {
      bToA.push(msg)
      await Promise.resolve()
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
  return { a, b, aToB, bToA }
}

async function flush(): Promise<void> {
  // Compression + decompression each add microtasks on top of the
  // existing handshake flow, so give more cycles than the e2ee tests.
  for (let i = 0; i < 20; i += 1) {
    await new Promise((r) => setTimeout(r, 0))
  }
}

describe.skipIf(!compressionAvailable())(
  'provider compression end-to-end',
  () => {
    it('sets z=true on large encrypted sync frames and round-trips cleanly', async () => {
      const keys = await freshKeys()
      const roomA = createCollabRoom({ selfPeerId: 'A', keys })
      const roomB = createCollabRoom({ selfPeerId: 'B', keys })
      const pair = makeTransportPair()
      roomA.addPeer(pair.a)
      roomB.addPeer(pair.b)

      // Seed a large Yjs update on A. 5000 integer array entries
      // comfortably exceeds the 1 KB compression threshold.
      const arr = roomA.doc.getArray<number>('big')
      roomA.doc.transact(() => {
        for (let i = 0; i < 5000; i++) arr.push([i])
      })

      await flush()

      // At least one outbound frame from A must carry z=true — that's
      // the big sync-2 update.
      const compressedFrames = pair.aToB.filter((m) => m.z === true)
      expect(compressedFrames.length).toBeGreaterThan(0)

      // Every compressed frame must also be encrypted (iv set).
      for (const m of compressedFrames) {
        expect(m.iv).toBeDefined()
      }

      const bArr = roomB.doc.getArray<number>('big')
      expect(bArr.length).toBe(5000)
      expect(bArr.get(0)).toBe(0)
      expect(bArr.get(4999)).toBe(4999)

      roomA.close()
      roomB.close()
    })

    it('small messages stay uncompressed (z flag absent)', async () => {
      const keys = await freshKeys()
      const roomA = createCollabRoom({ selfPeerId: 'A', keys })
      const roomB = createCollabRoom({ selfPeerId: 'B', keys })
      const pair = makeTransportPair()
      roomA.addPeer(pair.a)
      roomB.addPeer(pair.b)

      roomA.doc.getMap('m').set('k', 'v')
      await flush()

      // Every non-hello frame should omit ``z`` for a tiny edit.
      const nonHello = pair.aToB.filter((m) => m.t !== 'y-sync-hello')
      expect(nonHello.length).toBeGreaterThan(0)
      for (const m of nonHello) {
        expect(m.z).toBeUndefined()
      }

      roomA.close()
      roomB.close()
    })

    it('works with compression in plaintext mode too', async () => {
      const roomA = createCollabRoom({ selfPeerId: 'A' })
      const roomB = createCollabRoom({ selfPeerId: 'B' })
      const pair = makeTransportPair()
      roomA.addPeer(pair.a)
      roomB.addPeer(pair.b)

      const arr = roomA.doc.getArray<number>('big')
      roomA.doc.transact(() => {
        for (let i = 0; i < 5000; i++) arr.push([i])
      })
      await flush()

      // Plaintext mode: no iv, but z should still be true on the big
      // frame — compression is orthogonal to E2EE.
      const compressedFrames = pair.aToB.filter((m) => m.z === true)
      expect(compressedFrames.length).toBeGreaterThan(0)
      for (const m of compressedFrames) {
        expect(m.iv).toBeUndefined()
      }

      const bArr = roomB.doc.getArray<number>('big')
      expect(bArr.length).toBe(5000)

      roomA.close()
      roomB.close()
    })
  },
)
