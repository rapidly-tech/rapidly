import { describe, expect, it } from 'vitest'
import { Awareness } from 'y-protocols/awareness'
import * as Y from 'yjs'

import {
  awarenessPresenceSource,
  inMemoryPresenceSource,
  PRESENCE_PALETTE,
  stableColor,
} from './presence'

describe('stableColor', () => {
  it('returns a palette colour', () => {
    expect(PRESENCE_PALETTE).toContain(stableColor(1))
    expect(PRESENCE_PALETTE).toContain(stableColor(2 ** 30))
  })

  it('is deterministic for a given id', () => {
    expect(stableColor(1234)).toBe(stableColor(1234))
  })

  it('spreads low-entropy sequential ids across the palette', () => {
    // Sequential 0..7 should touch at least half the palette slots.
    const seen = new Set<string>()
    for (let i = 0; i < 8; i++) seen.add(stableColor(i))
    expect(seen.size).toBeGreaterThanOrEqual(PRESENCE_PALETTE.length / 2)
  })
})

describe('inMemoryPresenceSource', () => {
  it('starts with an empty remote list', () => {
    const src = inMemoryPresenceSource()
    expect(src.getRemotes()).toEqual([])
  })

  it('pushRemote adds a peer, removeRemote clears it', () => {
    const src = inMemoryPresenceSource()
    src.pushRemote({
      clientId: 1,
      user: { id: 'u1', color: '#e03131' },
      cursor: { x: 10, y: 20 },
    })
    expect(src.getRemotes()).toHaveLength(1)
    src.removeRemote(1)
    expect(src.getRemotes()).toEqual([])
  })

  it('subscribe fires on push and remove', () => {
    const src = inMemoryPresenceSource()
    let calls = 0
    const off = src.subscribe(() => {
      calls++
    })
    src.pushRemote({ clientId: 1, user: { id: 'u1', color: '#e03131' } })
    src.removeRemote(1)
    off()
    expect(calls).toBe(2)
    // After unsubscribe the listener is silent.
    src.pushRemote({ clientId: 2, user: { id: 'u2', color: '#e03131' } })
    expect(calls).toBe(2)
  })

  it('setLocal stores state and notifies subscribers', () => {
    const src = inMemoryPresenceSource()
    let calls = 0
    src.subscribe(() => {
      calls++
    })
    src.setLocal({
      user: { id: 'me', color: '#2f9e44' },
      cursor: { x: 1, y: 2 },
    })
    expect(src.local?.cursor).toEqual({ x: 1, y: 2 })
    expect(calls).toBe(1)
  })
})

describe('awarenessPresenceSource', () => {
  it('excludes the local client from getRemotes', () => {
    const doc = new Y.Doc()
    const aw = new Awareness(doc)
    const local = aw.clientID
    aw.setLocalState({ user: { id: 'me', color: '#1971c2' } })
    const src = awarenessPresenceSource(aw, local)
    expect(src.getRemotes()).toEqual([])
  })

  it('returns well-formed remote states', () => {
    const doc = new Y.Doc()
    const aw = new Awareness(doc)
    // Simulate a remote state by writing directly with a non-local
    // client id. Awareness doesn't expose a setState(id, ...) publicly,
    // so we inject via the internal states map for the test. This is
    // the same mechanism applyAwarenessUpdate uses.
    const states = aw.getStates() as Map<number, unknown>
    states.set(42, { user: { id: 'them', color: '#e03131', name: 'Them' } })
    const src = awarenessPresenceSource(aw, aw.clientID)
    const remotes = src.getRemotes()
    expect(remotes).toHaveLength(1)
    expect(remotes[0].clientId).toBe(42)
    expect(remotes[0].user.name).toBe('Them')
  })

  it('skips remotes missing required user fields', () => {
    const doc = new Y.Doc()
    const aw = new Awareness(doc)
    const states = aw.getStates() as Map<number, unknown>
    states.set(1, { user: { id: 'a', color: '#e03131' } }) // ok
    states.set(2, { user: { id: 'b' } }) // no colour — dropped
    states.set(3, {}) // no user — dropped
    states.set(4, { user: { color: '#e03131' } }) // no id — dropped
    const src = awarenessPresenceSource(aw, aw.clientID)
    const remotes = src.getRemotes()
    expect(remotes.map((r) => r.clientId).sort()).toEqual([1])
  })

  it('parses cursor and selection when present', () => {
    const doc = new Y.Doc()
    const aw = new Awareness(doc)
    const states = aw.getStates() as Map<number, unknown>
    states.set(7, {
      user: { id: 'x', color: '#e03131' },
      cursor: { x: 100, y: 200 },
      selection: ['el-1', 'el-2'],
    })
    const src = awarenessPresenceSource(aw, aw.clientID)
    const remote = src.getRemotes()[0]
    expect(remote.cursor).toEqual({ x: 100, y: 200 })
    expect(remote.selection).toEqual(['el-1', 'el-2'])
  })

  it('drops a malformed cursor rather than propagating NaN / strings', () => {
    const doc = new Y.Doc()
    const aw = new Awareness(doc)
    const states = aw.getStates() as Map<number, unknown>
    states.set(9, {
      user: { id: 'x', color: '#e03131' },
      cursor: { x: 'bogus', y: 5 },
    })
    const src = awarenessPresenceSource(aw, aw.clientID)
    const remote = src.getRemotes()[0]
    expect(remote.cursor).toBeUndefined()
  })

  it('setLocal strips undefined optional fields before publishing', () => {
    const doc = new Y.Doc()
    const aw = new Awareness(doc)
    const src = awarenessPresenceSource(aw, aw.clientID)
    src.setLocal({ user: { id: 'me', color: '#1971c2' } })
    const state = aw.getLocalState() as Record<string, unknown>
    expect(state.user).toBeDefined()
    expect('cursor' in state).toBe(false)
    expect('selection' in state).toBe(false)
  })

  it('setLocal carries cursor + selection when provided', () => {
    const doc = new Y.Doc()
    const aw = new Awareness(doc)
    const src = awarenessPresenceSource(aw, aw.clientID)
    src.setLocal({
      user: { id: 'me', color: '#1971c2' },
      cursor: { x: 50, y: 75 },
      selection: ['a', 'b'],
    })
    const state = aw.getLocalState() as Record<string, unknown>
    expect(state.cursor).toEqual({ x: 50, y: 75 })
    expect(state.selection).toEqual(['a', 'b'])
  })

  it('subscribe fires on awareness updates', () => {
    const doc = new Y.Doc()
    const aw = new Awareness(doc)
    const src = awarenessPresenceSource(aw, aw.clientID)
    let calls = 0
    const off = src.subscribe(() => {
      calls++
    })
    aw.setLocalState({ user: { id: 'me', color: '#1971c2' } })
    expect(calls).toBeGreaterThan(0)
    off()
    const before = calls
    aw.setLocalState({ user: { id: 'me', color: '#2f9e44' } })
    expect(calls).toBe(before)
  })
})
