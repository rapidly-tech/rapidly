import { describe, expect, it, vi } from 'vitest'

import {
  createFollowMeController,
  findRemote,
  viewportsEqual,
} from './follow-me'
import { inMemoryPresenceSource } from './presence'
import { makeViewport } from './viewport'

describe('viewportsEqual', () => {
  it('matches identical viewports', () => {
    const v = makeViewport({ scale: 2, scrollX: 10, scrollY: 20 })
    expect(viewportsEqual(v, { ...v })).toBe(true)
  })

  it('detects any field difference', () => {
    const v = makeViewport({ scale: 2 })
    expect(viewportsEqual(v, { ...v, scale: 2.1 })).toBe(false)
    expect(viewportsEqual(v, { ...v, scrollX: 1 })).toBe(false)
    expect(viewportsEqual(v, { ...v, scrollY: 1 })).toBe(false)
  })

  it('treats null / undefined consistently', () => {
    expect(viewportsEqual(null, null)).toBe(true)
    expect(viewportsEqual(undefined, undefined)).toBe(true)
    expect(viewportsEqual(null, undefined)).toBe(false)
    expect(viewportsEqual(null, makeViewport())).toBe(false)
  })
})

describe('findRemote', () => {
  it('returns the matching peer or null', () => {
    const a = {
      clientId: 1,
      user: { id: 'u1', color: '#e03131' },
    } as const
    const b = {
      clientId: 2,
      user: { id: 'u2', color: '#2f9e44' },
    } as const
    expect(findRemote([a, b], 2)).toBe(b)
    expect(findRemote([a, b], 99)).toBeNull()
    expect(findRemote([], 1)).toBeNull()
  })
})

describe('createFollowMeController', () => {
  it('starts inactive and reports null target', () => {
    const source = inMemoryPresenceSource()
    const apply = vi.fn()
    const ctrl = createFollowMeController({ source, apply })
    expect(ctrl.current()).toBeNull()
    ctrl.dispose()
  })

  it('applies the peer viewport immediately when target is set', () => {
    const source = inMemoryPresenceSource()
    const apply = vi.fn()
    source.pushRemote({
      clientId: 7,
      user: { id: 'x', color: '#e03131' },
      viewport: makeViewport({ scale: 2, scrollX: 100, scrollY: 200 }),
    })
    const ctrl = createFollowMeController({ source, apply })
    ctrl.setTarget(7)
    expect(apply).toHaveBeenCalledTimes(1)
    expect(apply.mock.calls[0][0]).toMatchObject({
      scale: 2,
      scrollX: 100,
      scrollY: 200,
    })
    ctrl.dispose()
  })

  it('follows subsequent viewport updates of the target', () => {
    const source = inMemoryPresenceSource()
    const apply = vi.fn()
    source.pushRemote({
      clientId: 7,
      user: { id: 'x', color: '#e03131' },
      viewport: makeViewport(),
    })
    const ctrl = createFollowMeController({ source, apply })
    ctrl.setTarget(7)
    apply.mockClear()

    source.pushRemote({
      clientId: 7,
      user: { id: 'x', color: '#e03131' },
      viewport: makeViewport({ scrollX: 50 }),
    })
    expect(apply).toHaveBeenCalledWith(expect.objectContaining({ scrollX: 50 }))
    ctrl.dispose()
  })

  it('does not re-apply when an unrelated field changes', () => {
    const source = inMemoryPresenceSource()
    const apply = vi.fn()
    const vp = makeViewport({ scrollX: 42 })
    source.pushRemote({
      clientId: 7,
      user: { id: 'x', color: '#e03131' },
      viewport: vp,
    })
    const ctrl = createFollowMeController({ source, apply })
    ctrl.setTarget(7)
    apply.mockClear()

    // Only cursor changes — viewport still {scrollX: 42, …}
    source.pushRemote({
      clientId: 7,
      user: { id: 'x', color: '#e03131' },
      viewport: { ...vp },
      cursor: { x: 1, y: 1 },
    })
    expect(apply).not.toHaveBeenCalled()
    ctrl.dispose()
  })

  it('skips apply when the target has no viewport published', () => {
    const source = inMemoryPresenceSource()
    const apply = vi.fn()
    source.pushRemote({
      clientId: 7,
      user: { id: 'x', color: '#e03131' },
      // no viewport
    })
    const ctrl = createFollowMeController({ source, apply })
    ctrl.setTarget(7)
    expect(apply).not.toHaveBeenCalled()
    ctrl.dispose()
  })

  it('setTarget(null) stops applying further updates', () => {
    const source = inMemoryPresenceSource()
    const apply = vi.fn()
    source.pushRemote({
      clientId: 7,
      user: { id: 'x', color: '#e03131' },
      viewport: makeViewport(),
    })
    const ctrl = createFollowMeController({ source, apply })
    ctrl.setTarget(7)
    apply.mockClear()
    ctrl.setTarget(null)
    source.pushRemote({
      clientId: 7,
      user: { id: 'x', color: '#e03131' },
      viewport: makeViewport({ scrollX: 999 }),
    })
    expect(apply).not.toHaveBeenCalled()
    expect(ctrl.current()).toBeNull()
    ctrl.dispose()
  })

  it('setTarget twice with the same id is a no-op', () => {
    const source = inMemoryPresenceSource()
    const apply = vi.fn()
    source.pushRemote({
      clientId: 7,
      user: { id: 'x', color: '#e03131' },
      viewport: makeViewport(),
    })
    const ctrl = createFollowMeController({ source, apply })
    ctrl.setTarget(7)
    apply.mockClear()
    ctrl.setTarget(7)
    expect(apply).not.toHaveBeenCalled()
    ctrl.dispose()
  })

  it('dispose unsubscribes and drops the target', () => {
    const source = inMemoryPresenceSource()
    const apply = vi.fn()
    source.pushRemote({
      clientId: 7,
      user: { id: 'x', color: '#e03131' },
      viewport: makeViewport(),
    })
    const ctrl = createFollowMeController({ source, apply })
    ctrl.setTarget(7)
    ctrl.dispose()
    apply.mockClear()
    source.pushRemote({
      clientId: 7,
      user: { id: 'x', color: '#e03131' },
      viewport: makeViewport({ scale: 3 }),
    })
    expect(apply).not.toHaveBeenCalled()
    expect(ctrl.current()).toBeNull()
  })
})
