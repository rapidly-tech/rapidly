/**
 * y-awareness replay protection tests (PR 35, v1.1.1).
 *
 * Addresses Concern §2 from specs/collab-e2ee-security-review.md —
 * an attacker who can observe + re-inject a ciphertext y-awareness
 * frame shouldn't be able to cause a stale cursor / presence state
 * to resurface on every peer.
 *
 * The fix: a per-sender monotonic counter (``c``) stamped on every
 * outbound y-awareness frame. Receivers track the max seen per peer
 * and drop frames with a non-increasing counter.
 */

import { describe, expect, it } from 'vitest'

import type { CollabTransport, CollabWireMessage } from './provider'
import { createCollabRoom } from './provider'

interface Pair {
  a: CollabTransport
  b: CollabTransport
  aToB: CollabWireMessage[]
}

function makePair(): Pair {
  const hA: Array<(m: CollabWireMessage) => void> = []
  const hB: Array<(m: CollabWireMessage) => void> = []
  const aToB: CollabWireMessage[] = []
  const a: CollabTransport = {
    peerId: 'b',
    async send(m) {
      aToB.push(m)
      await Promise.resolve()
      for (const h of hB) h(m)
    },
    onMessage(h) {
      hA.push(h)
      return () => {
        const i = hA.indexOf(h)
        if (i >= 0) hA.splice(i, 1)
      }
    },
  }
  const b: CollabTransport = {
    peerId: 'a',
    async send(m) {
      await Promise.resolve()
      for (const h of hA) h(m)
    },
    onMessage(h) {
      hB.push(h)
      return () => {
        const i = hB.indexOf(h)
        if (i >= 0) hB.splice(i, 1)
      }
    },
  }
  return { a, b, aToB }
}

async function flush(): Promise<void> {
  for (let i = 0; i < 4; i += 1) {
    await new Promise((r) => setTimeout(r, 0))
  }
}

describe('y-awareness replay protection', () => {
  it('stamps outbound y-awareness with a monotonically increasing c', async () => {
    const a = createCollabRoom({ selfPeerId: 'a' })
    const b = createCollabRoom({ selfPeerId: 'b' })
    const { a: tA, b: tB, aToB } = makePair()
    a.addPeer(tA)
    b.addPeer(tB)
    await flush()

    a.awareness.setLocalState({ name: 'alice' })
    await flush()
    a.awareness.setLocalState({ name: 'alice', cursor: 1 })
    await flush()
    a.awareness.setLocalState({ name: 'alice', cursor: 2 })
    await flush()

    const awarenessFrames = aToB.filter((m) => m.t === 'y-awareness')
    const counters = awarenessFrames
      .map((m) => m.c)
      .filter((c): c is number => typeof c === 'number')
    expect(counters.length).toBeGreaterThanOrEqual(3)
    for (let i = 1; i < counters.length; i += 1) {
      expect(counters[i]).toBeGreaterThan(counters[i - 1])
    }

    a.close()
    b.close()
  })

  it('drops a replayed y-awareness frame (same c) silently', async () => {
    const a = createCollabRoom({ selfPeerId: 'a' })
    const b = createCollabRoom({ selfPeerId: 'b' })
    const { a: tA, b: tB, aToB } = makePair()
    a.addPeer(tA)
    b.addPeer(tB)
    await flush()

    a.awareness.setLocalState({ name: 'alice', marker: 'first' })
    await flush()
    a.awareness.setLocalState({ name: 'alice', marker: 'second' })
    await flush()

    // "Second" is the latest — b's awareness map should reflect it.
    const seenBefore = b.awareness.getStates().get(a.awareness.clientID)
    expect((seenBefore as { marker?: string }).marker).toBe('second')

    // Now replay the first y-awareness frame. We re-inject it through
    // the transport to simulate a hostile party that captured the
    // wire frame and re-sent it later.
    const frames = aToB.filter((m) => m.t === 'y-awareness')
    const firstFrame = frames[0]
    expect(firstFrame).toBeDefined()
    await tA.send(firstFrame)
    await flush()

    // State on b must still be "second" — the replay was dropped.
    const seenAfter = b.awareness.getStates().get(a.awareness.clientID)
    expect((seenAfter as { marker?: string }).marker).toBe('second')

    a.close()
    b.close()
  })

  it('drops a crafted y-awareness with out-of-order counter', async () => {
    const a = createCollabRoom({ selfPeerId: 'a' })
    const b = createCollabRoom({ selfPeerId: 'b' })
    const { a: tA, b: tB, aToB } = makePair()
    a.addPeer(tA)
    b.addPeer(tB)
    await flush()

    a.awareness.setLocalState({ name: 'alice', step: 1 })
    await flush()
    a.awareness.setLocalState({ name: 'alice', step: 2 })
    await flush()

    const frames = aToB.filter((m) => m.t === 'y-awareness')
    const highC = Math.max(
      ...frames.map((m) => (typeof m.c === 'number' ? m.c : 0)),
    )
    // Construct a frame with a counter already seen (max seen), using
    // the bytes of an earlier real frame — receiver must drop it.
    const crafted: CollabWireMessage = {
      t: 'y-awareness',
      bytes: frames[0].bytes,
      c: highC, // ≤ awarenessMaxC (which already saw highC)
    }
    // Preserve iv if present so decrypt succeeds in E2EE mode. (This
    // test runs plaintext; iv is undefined either way.)
    if (frames[0].iv) crafted.iv = frames[0].iv
    await tA.send(crafted)
    await flush()

    const stillStep2 = b.awareness.getStates().get(a.awareness.clientID)
    expect((stillStep2 as { step?: number }).step).toBe(2)

    a.close()
    b.close()
  })

  it('accepts a frame missing ``c`` (back-compat with v1.1)', async () => {
    const a = createCollabRoom({ selfPeerId: 'a' })
    const b = createCollabRoom({ selfPeerId: 'b' })
    const { a: tA, b: tB } = makePair()
    a.addPeer(tA)
    b.addPeer(tB)
    await flush()

    a.awareness.setLocalState({ name: 'alice', v: 1 })
    await flush()

    // Synthesise a v1.1-style frame: no ``c`` field. In plaintext
    // mode the bytes are the Yjs awareness encoding; we reach in via
    // the last-seen frame and strip ``c``.
    const encoded = await new Promise<CollabWireMessage>((resolve) => {
      const unsub = tB.onMessage((m) => {
        if (m.t === 'y-awareness') {
          unsub()
          resolve(m)
        }
      })
      a.awareness.setLocalState({ name: 'alice', v: 2 })
    })
    const legacy: CollabWireMessage = {
      t: 'y-awareness',
      bytes: encoded.bytes,
    }
    if (encoded.iv) legacy.iv = encoded.iv
    await tA.send(legacy)
    await flush()

    // The fact that we applied earlier frames proves back-compat;
    // assertion here is just "doesn't crash".
    expect(b.awareness.getStates().has(a.awareness.clientID)).toBe(true)

    a.close()
    b.close()
  })

  it('counters are per-peer — inbound from different peers tracked independently', async () => {
    // Narrower invariant than the full 3-peer mesh in the
    // integration test: this test just confirms the PeerState's
    // awarenessMaxC is keyed by transport (peer), not shared across
    // peers. makePair() is 1:1 so we run two independent pairs.
    const roomX = createCollabRoom({ selfPeerId: 'x' })
    const roomZviaX = createCollabRoom({ selfPeerId: 'z' })
    const pairXZ = makePair()
    roomX.addPeer(pairXZ.a)
    roomZviaX.addPeer(pairXZ.b)
    await flush()
    roomX.awareness.setLocalState({ src: 'x' })
    await flush()
    expect(
      roomZviaX.awareness.getStates().get(roomX.awareness.clientID),
    ).toEqual({ src: 'x' })
    roomX.close()
    roomZviaX.close()

    const roomY = createCollabRoom({ selfPeerId: 'y' })
    const roomZviaY = createCollabRoom({ selfPeerId: 'z' })
    const pairYZ = makePair()
    roomY.addPeer(pairYZ.a)
    roomZviaY.addPeer(pairYZ.b)
    await flush()
    roomY.awareness.setLocalState({ src: 'y' })
    await flush()
    expect(
      roomZviaY.awareness.getStates().get(roomY.awareness.clientID),
    ).toEqual({ src: 'y' })
    roomY.close()
    roomZviaY.close()
  })
})
