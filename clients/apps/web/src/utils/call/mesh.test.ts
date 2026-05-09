/**
 * Unit tests for the N-way Call mesh coordinator (PR 14).
 *
 * No WebRTC, no signaling, no DOM — a hand-rolled FakePeer stands in
 * for PeerDataConnection. Exercises the interesting behaviour:
 *
 *   - setParticipants is additive (new peers open)
 *   - setParticipants is subtractive (departed peers close)
 *   - setParticipants is idempotent (repeat input = no-op)
 *   - shouldInitiateOffer tie-breaker: lower peer ID calls createOffer
 *   - publishTrack pushes to existing and future peers
 *   - the self peer is skipped in the participant list
 *   - close() tears everything down
 */

import { describe, expect, it, vi } from 'vitest'

import { createMesh, shouldInitiateOffer, type PeerLike } from './mesh'

// ── Fake peer ──

function makeFakePeer(remote: string): PeerLike & {
  createOfferCalls: number
  addTrackCalls: Array<{
    track: MediaStreamTrack
    stream: MediaStream
  }>
  closeCalls: number
  triggerClose(): void
  triggerTrack(track: MediaStreamTrack, streams: MediaStream[]): void
} {
  const fake = {
    open: true,
    peer: remote,
    createOfferCalls: 0,
    addTrackCalls: [] as Array<{
      track: MediaStreamTrack
      stream: MediaStream
    }>,
    closeCalls: 0,
    onOpen: null as (() => void) | null,
    onClose: null as (() => void) | null,
    onTrack: null as
      | ((track: MediaStreamTrack, streams: readonly MediaStream[]) => void)
      | null,
    async createOffer(): Promise<void> {
      this.createOfferCalls++
    },
    addTrack(track: MediaStreamTrack, stream: MediaStream): unknown {
      this.addTrackCalls.push({ track, stream })
      return {}
    },
    close(): void {
      this.closeCalls++
      this.open = false
      this.onClose?.()
    },
    triggerClose(): void {
      this.onClose?.()
    },
    triggerTrack(track: MediaStreamTrack, streams: MediaStream[]): void {
      this.onTrack?.(track, streams)
    },
  }
  return fake
}

function makeTrack(): MediaStreamTrack {
  return { id: 't' + Math.random() } as unknown as MediaStreamTrack
}
function makeStream(): MediaStream {
  return { id: 's' } as unknown as MediaStream
}

// ── Tie-breaker ──

describe('shouldInitiateOffer', () => {
  it('lower peer ID initiates', () => {
    expect(shouldInitiateOffer('a', 'b')).toBe(true)
    expect(shouldInitiateOffer('b', 'a')).toBe(false)
  })

  it('both sides reach opposite decisions for any pair', () => {
    // Property: for any distinct IDs, exactly one of the two calls is
    // truthy. This is the contract that prevents glare.
    const ids = ['alpha', 'beta', 'gamma', '0001', 'zz', 'a']
    for (const a of ids) {
      for (const b of ids) {
        if (a === b) continue
        const left = shouldInitiateOffer(a, b)
        const right = shouldInitiateOffer(b, a)
        expect(left).not.toBe(right)
      }
    }
  })
})

// ── Coordinator ──

describe('createMesh', () => {
  function harness(self = 'self') {
    const factoryCalls: string[] = []
    const created = new Map<string, ReturnType<typeof makeFakePeer>>()

    const onPeerAdded = vi.fn()
    const onPeerRemoved = vi.fn()
    const onRemoteTrack = vi.fn()

    const mesh = createMesh(
      self,
      (remote) => {
        factoryCalls.push(remote)
        const peer = makeFakePeer(remote)
        created.set(remote, peer)
        return peer
      },
      { onPeerAdded, onPeerRemoved, onRemoteTrack },
    )
    return {
      mesh,
      created,
      factoryCalls,
      onPeerAdded,
      onPeerRemoved,
      onRemoteTrack,
    }
  }

  it('opens a connection for each participant (except self)', () => {
    const h = harness('self')
    h.mesh.setParticipants(['self', 'alice', 'bob'])
    expect(h.factoryCalls.sort()).toEqual(['alice', 'bob'])
    expect(h.mesh.peers.size).toBe(2)
    expect(h.onPeerAdded).toHaveBeenCalledTimes(2)
  })

  it('skips the self peer even if present in the list', () => {
    const h = harness('self')
    h.mesh.setParticipants(['self'])
    expect(h.mesh.peers.size).toBe(0)
  })

  it('initiates offer only when self < remote (tie-breaker)', () => {
    const h = harness('m') // 'a' < 'm' < 'z'
    h.mesh.setParticipants(['a', 'z'])
    // self='m': 'a' is lower than 'm' → wait. 'z' is higher → offer.
    expect(h.created.get('a')!.createOfferCalls).toBe(0)
    expect(h.created.get('z')!.createOfferCalls).toBe(1)
  })

  it('is idempotent when called twice with the same list', () => {
    const h = harness('self')
    h.mesh.setParticipants(['alice', 'bob'])
    h.mesh.setParticipants(['alice', 'bob'])
    expect(h.factoryCalls).toEqual(['alice', 'bob'])
    expect(h.mesh.peers.size).toBe(2)
  })

  it('closes and removes peers that disappear from the roster', () => {
    const h = harness('self')
    h.mesh.setParticipants(['alice', 'bob'])
    h.mesh.setParticipants(['alice']) // bob left

    expect(h.mesh.peers.has('alice')).toBe(true)
    expect(h.mesh.peers.has('bob')).toBe(false)
    expect(h.created.get('bob')!.closeCalls).toBe(1)
    expect(h.onPeerRemoved).toHaveBeenCalledWith('bob')
  })

  it('adds new peers on a subsequent setParticipants call', () => {
    const h = harness('self')
    h.mesh.setParticipants(['alice'])
    h.mesh.setParticipants(['alice', 'bob']) // bob joins
    expect(h.mesh.peers.size).toBe(2)
    expect(h.factoryCalls).toEqual(['alice', 'bob'])
  })

  it('fans out publishTrack to every current peer', () => {
    const h = harness('self')
    h.mesh.setParticipants(['alice', 'bob'])
    const t = makeTrack()
    const s = makeStream()

    h.mesh.publishTrack(t, s)

    expect(h.created.get('alice')!.addTrackCalls).toContainEqual({
      track: t,
      stream: s,
    })
    expect(h.created.get('bob')!.addTrackCalls).toContainEqual({
      track: t,
      stream: s,
    })
  })

  it('replays published tracks to peers that join after publishTrack', () => {
    const h = harness('self')
    const t = makeTrack()
    const s = makeStream()

    // Publish BEFORE any peers exist.
    h.mesh.publishTrack(t, s)
    h.mesh.setParticipants(['alice'])

    expect(h.created.get('alice')!.addTrackCalls).toContainEqual({
      track: t,
      stream: s,
    })
  })

  it('forwards remote tracks to onRemoteTrack with the right peerId', () => {
    const h = harness('self')
    h.mesh.setParticipants(['alice'])
    const peer = h.created.get('alice')!
    const t = makeTrack()
    const s = makeStream()

    peer.triggerTrack(t, [s])

    expect(h.onRemoteTrack).toHaveBeenCalledWith('alice', t, [s])
  })

  it('auto-removes a peer when its underlying connection closes unsolicited', () => {
    const h = harness('self')
    h.mesh.setParticipants(['alice'])
    h.created.get('alice')!.triggerClose()

    expect(h.mesh.peers.has('alice')).toBe(false)
    expect(h.onPeerRemoved).toHaveBeenCalledWith('alice')
  })

  it('close() tears every peer down and forgets published tracks', () => {
    const h = harness('self')
    h.mesh.publishTrack(makeTrack(), makeStream())
    h.mesh.setParticipants(['alice', 'bob'])

    h.mesh.close()

    expect(h.created.get('alice')!.closeCalls).toBe(1)
    expect(h.created.get('bob')!.closeCalls).toBe(1)
    expect(h.mesh.peers.size).toBe(0)

    // New peer joining post-close should not re-receive the published
    // track — the coordinator cleared its buffer.
    h.mesh.setParticipants(['charlie'])
    expect(h.created.get('charlie')!.addTrackCalls).toEqual([])
  })
})
