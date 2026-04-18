/**
 * Collab provider — E2EE handshake + envelope tests (PR 24).
 *
 * Pins the behaviour introduced by v1.1 PR B:
 *
 *   - Two E2EE peers converge with encrypted frames on the wire.
 *   - An E2EE peer and a plaintext peer still converge (rolling-deploy
 *     safety — both sides see plaintext after the handshake).
 *   - Frames with the wrong ``iv`` or key are dropped without crashing.
 *   - ``peerEncryptionStatus`` reports ``pending`` → ``e2ee`` or
 *     ``plaintext`` exactly once.
 *
 * No real crypto stubs — uses the real ``utils/crypto/*`` primitives
 * so the tests exercise the actual Web Crypto path.
 */

import { describe, expect, it } from 'vitest'

import { generateMasterKey, generateSalt } from '@/utils/crypto/master-key'

import type { CollabTransport, CollabWireMessage } from './provider'
import { createCollabRoom, deriveCollabKeys } from './provider'

interface TransportPair {
  a: CollabTransport
  b: CollabTransport
  /** Tap every frame that crossed from A→B. Tests use it to assert
   *  that ciphertext (not plaintext Yjs updates) is what's on the wire. */
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
  // Handshake + sync-1 + sync-2 need a few microtask cycles to settle.
  for (let i = 0; i < 6; i += 1) {
    await new Promise((r) => setTimeout(r, 0))
  }
}

describe('CollabRoom — E2EE two-peer', () => {
  it('both peers with keys converge and frames on the wire carry an iv', async () => {
    const master = await generateMasterKey()
    const salt = generateSalt()
    const keys = await deriveCollabKeys(master, salt)

    const roomA = createCollabRoom({ selfPeerId: 'a', keys })
    const roomB = createCollabRoom({ selfPeerId: 'b', keys })
    const { a, b, aToB } = makeTransportPair()
    roomA.addPeer(a)
    roomB.addPeer(b)
    await flush()

    expect(roomA.peerEncryptionStatus('b')).toBe('e2ee')
    expect(roomB.peerEncryptionStatus('a')).toBe('e2ee')

    roomA.doc.getText('t').insert(0, 'secret')
    await flush()
    expect(roomB.doc.getText('t').toString()).toBe('secret')

    // At least one y-sync-2 frame was ciphertext — the iv field
    // presence is the boundary signal. (The hello itself carries no iv.)
    const syncFrames = aToB.filter((m) => m.t === 'y-sync-2')
    expect(syncFrames.length).toBeGreaterThan(0)
    expect(syncFrames.every((m) => m.iv instanceof Uint8Array)).toBe(true)
    // And those ciphertexts must NOT contain the plaintext "secret".
    for (const m of syncFrames) {
      const plaintextInCiphertext = new TextDecoder().decode(m.bytes)
      expect(plaintextInCiphertext).not.toContain('secret')
    }

    roomA.close()
    roomB.close()
  })

  it('mixed peers (one with keys, one without) converge in plaintext', async () => {
    // Rolling-deploy safety: a v1.1 client talking to a v1 client
    // must still function. Handshake falls back to plaintext.
    const master = await generateMasterKey()
    const salt = generateSalt()
    const keys = await deriveCollabKeys(master, salt)

    const roomA = createCollabRoom({ selfPeerId: 'a', keys }) // v1.1
    const roomB = createCollabRoom({ selfPeerId: 'b' }) // v1
    const { a, b, aToB } = makeTransportPair()
    roomA.addPeer(a)
    roomB.addPeer(b)
    await flush()

    expect(roomA.peerEncryptionStatus('b')).toBe('plaintext')
    expect(roomB.peerEncryptionStatus('a')).toBe('plaintext')

    roomA.doc.getText('t').insert(0, 'mixed')
    await flush()
    expect(roomB.doc.getText('t').toString()).toBe('mixed')

    // No iv anywhere on the wire once we fell back.
    for (const m of aToB) expect(m.iv).toBeUndefined()

    roomA.close()
    roomB.close()
  })

  it('different master keys on the two peers produce garbage on decrypt — drop, no crash', async () => {
    const salt = generateSalt()
    const keysA = await deriveCollabKeys(await generateMasterKey(), salt)
    const keysB = await deriveCollabKeys(await generateMasterKey(), salt)

    const roomA = createCollabRoom({ selfPeerId: 'a', keys: keysA })
    const roomB = createCollabRoom({ selfPeerId: 'b', keys: keysB })
    const { a, b } = makeTransportPair()
    roomA.addPeer(a)
    roomB.addPeer(b)
    await flush()

    // Both advertised e2ee, so they settled on e2ee. But the keys
    // don't match — every incoming frame fails decrypt. No crash,
    // just no convergence.
    expect(roomA.peerEncryptionStatus('b')).toBe('e2ee')
    expect(roomB.peerEncryptionStatus('a')).toBe('e2ee')

    roomA.doc.getText('t').insert(0, 'never-seen')
    await flush()
    expect(roomB.doc.getText('t').toString()).toBe('')

    // And the room is still responsive — local edits on B work.
    roomB.doc.getText('t').insert(0, 'local-b')
    await flush()
    expect(roomB.doc.getText('t').toString()).toBe('local-b')

    roomA.close()
    roomB.close()
  })

  it('peerEncryptionStatus reports pending before hello lands, then resolves', async () => {
    const master = await generateMasterKey()
    const keys = await deriveCollabKeys(master, generateSalt())
    const roomA = createCollabRoom({ selfPeerId: 'a', keys })
    const roomB = createCollabRoom({ selfPeerId: 'b', keys })
    const { a, b } = makeTransportPair()

    roomA.addPeer(a)
    // Before B adds, A has no hello reply → pending.
    expect(roomA.peerEncryptionStatus('b')).toBe('pending')

    roomB.addPeer(b)
    await flush()
    expect(roomA.peerEncryptionStatus('b')).toBe('e2ee')
    expect(roomA.peerEncryptionStatus('nonexistent')).toBeNull()

    roomA.close()
    roomB.close()
  })

  it('awareness propagates under E2EE', async () => {
    const master = await generateMasterKey()
    const keys = await deriveCollabKeys(master, generateSalt())
    const roomA = createCollabRoom({ selfPeerId: 'a', keys })
    const roomB = createCollabRoom({ selfPeerId: 'b', keys })
    const { a, b, aToB } = makeTransportPair()
    roomA.addPeer(a)
    roomB.addPeer(b)
    await flush()

    roomA.awareness.setLocalState({ name: 'encrypted-alice' })
    await flush()

    const entry = roomB.awareness.getStates().get(roomA.awareness.clientID)
    expect(entry).toEqual({ name: 'encrypted-alice' })

    // Awareness frames on the wire must also have an iv.
    const awFrames = aToB.filter((m) => m.t === 'y-awareness')
    expect(awFrames.length).toBeGreaterThan(0)
    expect(awFrames.every((m) => m.iv instanceof Uint8Array)).toBe(true)

    roomA.close()
    roomB.close()
  })
})
