/**
 * Cross-tab sync — pinned behaviour:
 *
 * - Two docs sharing the same channel converge on edits in either.
 * - CROSS_TAB_ORIGIN tags inbound updates so doc handlers can skip.
 * - Inbound updates don't echo back to the sender.
 * - Hello triggers a state-vector exchange so a late tab catches up
 *   on history without an extra edit.
 * - Different room ids get different channels.
 * - Malformed messages are dropped.
 * - Dispose tears down the channel + listener.
 * - SSR: no BroadcastChannel → controller is inactive but safe.
 */

import { describe, expect, it, vi } from 'vitest'
import * as Y from 'yjs'

import {
  CROSS_TAB_ORIGIN,
  channelNameFor,
  createCrossTabSync,
  type CrossTabChannel,
  type CrossTabChannelFactory,
} from './cross-tab-sync'

/** Build a pair of in-memory channels that share a single message bus
 *  per name. Mirrors how two tabs see the same BroadcastChannel. */
function busFactory(): {
  factory: CrossTabChannelFactory
  channels: Map<string, CrossTabChannel[]>
} {
  const channels = new Map<string, CrossTabChannel[]>()
  const factory: CrossTabChannelFactory = (name) => {
    const peers = channels.get(name) ?? []
    const listeners: Array<(e: { data: unknown }) => void> = []
    const ch: CrossTabChannel = {
      postMessage(data) {
        // Fan out to every peer except this one (BroadcastChannel
        // doesn't echo back to the sender either).
        for (const p of peers) {
          if (p === ch) continue
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          for (const l of (p as any).__listeners) l({ data })
        }
      },
      addEventListener(_type, listener) {
        listeners.push(listener)
      },
      removeEventListener(_type, listener) {
        const i = listeners.indexOf(listener)
        if (i >= 0) listeners.splice(i, 1)
      },
      close() {
        const i = peers.indexOf(ch)
        if (i >= 0) peers.splice(i, 1)
      },
    }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ;(ch as any).__listeners = listeners
    peers.push(ch)
    channels.set(name, peers)
    return ch
  }
  return { factory, channels }
}

describe('createCrossTabSync', () => {
  it('returns inactive when BroadcastChannel is unavailable', () => {
    const ctrl = createCrossTabSync({
      doc: new Y.Doc(),
      roomId: 'r',
      channelFactory: () => null,
    })
    expect(ctrl.active).toBe(false)
    ctrl.dispose() // safe to call
  })

  it('forwards local updates to a sibling tab on the same channel', () => {
    const { factory } = busFactory()
    const docA = new Y.Doc()
    const docB = new Y.Doc()
    const a = createCrossTabSync({
      doc: docA,
      roomId: 'room',
      channelFactory: factory,
    })
    const b = createCrossTabSync({
      doc: docB,
      roomId: 'room',
      channelFactory: factory,
    })

    docA.getMap('m').set('k', 1)
    expect((docB.getMap('m').get('k') as number) ?? null).toBe(1)
    a.dispose()
    b.dispose()
  })

  it('tags inbound updates with CROSS_TAB_ORIGIN', () => {
    const { factory } = busFactory()
    const docA = new Y.Doc()
    const docB = new Y.Doc()
    const a = createCrossTabSync({
      doc: docA,
      roomId: 'r',
      channelFactory: factory,
    })
    const b = createCrossTabSync({
      doc: docB,
      roomId: 'r',
      channelFactory: factory,
    })
    let observed: unknown = 'unset'
    docB.on('update', (_u, origin) => {
      observed = origin
    })
    docA.getMap('m').set('k', 1)
    expect(observed).toBe(CROSS_TAB_ORIGIN)
    a.dispose()
    b.dispose()
  })

  it('does not echo inbound updates back to the sender', () => {
    const { factory } = busFactory()
    const docA = new Y.Doc()
    const docB = new Y.Doc()
    const a = createCrossTabSync({
      doc: docA,
      roomId: 'r',
      channelFactory: factory,
    })
    const b = createCrossTabSync({
      doc: docB,
      roomId: 'r',
      channelFactory: factory,
    })
    let bUpdates = 0
    docB.on('update', () => {
      bUpdates++
    })
    docA.getMap('m').set('k', 1)
    expect(bUpdates).toBe(1) // exactly one apply on B; no echo
    a.dispose()
    b.dispose()
  })

  it('catches up a late tab via hello → state-vector exchange', () => {
    const { factory } = busFactory()
    const docA = new Y.Doc()
    docA.getMap('m').set('past', 'edit')
    const a = createCrossTabSync({
      doc: docA,
      roomId: 'r',
      channelFactory: factory,
    })

    // Late tab joins after some history exists.
    const docB = new Y.Doc()
    const b = createCrossTabSync({
      doc: docB,
      roomId: 'r',
      channelFactory: factory,
    })
    expect(docB.getMap('m').get('past')).toBe('edit')
    a.dispose()
    b.dispose()
  })

  it('isolates rooms — different ids do not cross-talk', () => {
    const { factory } = busFactory()
    const docA = new Y.Doc()
    const docB = new Y.Doc()
    const a = createCrossTabSync({
      doc: docA,
      roomId: 'r1',
      channelFactory: factory,
    })
    const b = createCrossTabSync({
      doc: docB,
      roomId: 'r2',
      channelFactory: factory,
    })
    docA.getMap('m').set('k', 1)
    expect(docB.getMap('m').get('k')).toBeUndefined()
    a.dispose()
    b.dispose()
  })

  it('drops malformed inbound messages', () => {
    const { factory, channels } = busFactory()
    const docA = new Y.Doc()
    const ctrl = createCrossTabSync({
      doc: docA,
      roomId: 'r',
      channelFactory: factory,
    })
    const peers = channels.get('rapidly-collab-r')!
    // Send a few garbage payloads from a synthetic peer.
    const garbage = [
      null,
      'string',
      42,
      { type: 'unknown' },
      { type: 'update' /* missing payload */ },
      { type: 'update', payload: 'not bytes' },
      { type: 'state-vector' /* missing payload */ },
    ]
    for (const g of garbage) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      for (const l of (peers[0] as any).__listeners) l({ data: g })
    }
    // Doc should still be empty + functional.
    expect(docA.getMap('m').size).toBe(0)
    docA.getMap('m').set('k', 1)
    expect(docA.getMap('m').get('k')).toBe(1)
    ctrl.dispose()
  })

  it('dispose tears down channel + listener and is idempotent', () => {
    const close = vi.fn()
    const ch: CrossTabChannel = {
      postMessage: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      close,
    }
    const ctrl = createCrossTabSync({
      doc: new Y.Doc(),
      roomId: 'r',
      channelFactory: () => ch,
    })
    expect(ctrl.active).toBe(true)
    ctrl.dispose()
    ctrl.dispose() // idempotent
    expect(close).toHaveBeenCalledTimes(1)
  })
})

describe('channelNameFor', () => {
  it('namespaces by room id', () => {
    expect(channelNameFor('alpha')).not.toBe(channelNameFor('beta'))
    expect(channelNameFor('alpha')).toContain('alpha')
  })
})
