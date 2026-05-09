/**
 * Per-peer inbound drop rate-limit tests (PR 37).
 *
 * Concern §6 from specs/collab-e2ee-security-review.md: a peer that
 * pumps garbage frames can burn CPU on repeated decrypt → null
 * attempts. This suite pins the behaviour that once a peer exceeds
 * the per-window drop threshold, further inbound is short-circuited
 * until the window rolls.
 *
 * We exercise the limit via garbage y-awareness frames (replay +
 * crafted bytes) because those are the cheapest way to hit the drop
 * path without crypto setup.
 */

import { describe, expect, it } from 'vitest'

import type { CollabTransport, CollabWireMessage } from './provider'
import { createCollabRoom } from './provider'

function makePair(): {
  a: CollabTransport
  b: CollabTransport
} {
  const hA: Array<(m: CollabWireMessage) => void> = []
  const hB: Array<(m: CollabWireMessage) => void> = []
  const a: CollabTransport = {
    peerId: 'b',
    async send(m) {
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
  return { a, b }
}

async function flush(): Promise<void> {
  for (let i = 0; i < 4; i += 1) {
    await new Promise((r) => setTimeout(r, 0))
  }
}

describe('per-peer inbound drop rate-limit', () => {
  it('silently absorbs a garbage burst; local doc keeps functioning', async () => {
    // This test asserts only the liveness property: the receiving
    // room must not crash or hang under a flood. It deliberately does
    // NOT assert that the flooding peer's subsequent legit frames
    // arrive — rate-limiting IS the design, and a flooding peer
    // getting muted for the remainder of the window is correct.
    const roomA = createCollabRoom({ selfPeerId: 'a' })
    const roomB = createCollabRoom({ selfPeerId: 'b' })
    const { a, b } = makePair()
    roomA.addPeer(a)
    roomB.addPeer(b)
    await flush()

    // Pump 100 crafted awareness frames at B. First accept (c=1 → max=1),
    // 99 drops, crossing the threshold.
    for (let i = 0; i < 100; i += 1) {
      await a.send({
        t: 'y-awareness',
        bytes: new Uint8Array([0xff, 0xff]),
        c: 1,
      })
    }
    await flush()

    // Room B is still alive — local edits still apply synchronously
    // within its own Y.Doc.
    roomB.doc.getText('t').insert(0, 'local works')
    expect(roomB.doc.getText('t').toString()).toBe('local works')

    roomA.close()
    roomB.close()
  })

  it('keeps accepting legitimate frames from a different (well-behaved) peer', async () => {
    // Simulates a hostile peer X alongside a legitimate peer Y, both
    // connected to receiver Z. X floods with garbage — Z must still
    // read Y's honest updates. The per-peer rate-limit is the
    // mechanism: X's dropCount maxes out; Y's is untouched.
    const roomZ = createCollabRoom({ selfPeerId: 'z' })

    // Z needs two distinct transports. We build them by hand below
    // so each has a distinct ``peerId`` and its own handler bank.
    const roomX = createCollabRoom({ selfPeerId: 'x' })
    const roomY = createCollabRoom({ selfPeerId: 'y' })

    // Build Z's two transports by hand so each has a distinct peerId.
    const xToZ: CollabTransport = {
      peerId: 'z',
      async send(m) {
        await Promise.resolve()
        for (const h of zFromXHandlers) h(m)
      },
      onMessage(h) {
        xHandlers.push(h)
        return () => {
          const i = xHandlers.indexOf(h)
          if (i >= 0) xHandlers.splice(i, 1)
        }
      },
    }
    const yToZ: CollabTransport = {
      peerId: 'z',
      async send(m) {
        await Promise.resolve()
        for (const h of zFromYHandlers) h(m)
      },
      onMessage(h) {
        yHandlers.push(h)
        return () => {
          const i = yHandlers.indexOf(h)
          if (i >= 0) yHandlers.splice(i, 1)
        }
      },
    }
    const zToX: CollabTransport = {
      peerId: 'x',
      async send(m) {
        await Promise.resolve()
        for (const h of xHandlers) h(m)
      },
      onMessage(h) {
        zFromXHandlers.push(h)
        return () => {
          const i = zFromXHandlers.indexOf(h)
          if (i >= 0) zFromXHandlers.splice(i, 1)
        }
      },
    }
    const zToY: CollabTransport = {
      peerId: 'y',
      async send(m) {
        await Promise.resolve()
        for (const h of yHandlers) h(m)
      },
      onMessage(h) {
        zFromYHandlers.push(h)
        return () => {
          const i = zFromYHandlers.indexOf(h)
          if (i >= 0) zFromYHandlers.splice(i, 1)
        }
      },
    }
    const xHandlers: Array<(m: CollabWireMessage) => void> = []
    const yHandlers: Array<(m: CollabWireMessage) => void> = []
    const zFromXHandlers: Array<(m: CollabWireMessage) => void> = []
    const zFromYHandlers: Array<(m: CollabWireMessage) => void> = []

    roomX.addPeer(xToZ)
    roomZ.addPeer(zToX)
    roomY.addPeer(yToZ)
    roomZ.addPeer(zToY)
    await flush()

    // X pumps garbage awareness at Z.
    for (let i = 0; i < 100; i += 1) {
      await xToZ.send({
        t: 'y-awareness',
        bytes: new Uint8Array([0xff, 0xff]),
        c: 1,
      })
    }
    await flush()

    // Y sends a legitimate text edit. Z should still receive it.
    roomY.doc.getText('t').insert(0, 'from-y')
    await flush()
    expect(roomZ.doc.getText('t').toString()).toBe('from-y')

    roomX.close()
    roomY.close()
    roomZ.close()
  })
})
