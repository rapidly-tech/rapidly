import { describe, expect, it, vi } from 'vitest'

import { SelectionState } from './selection'

describe('SelectionState', () => {
  it('starts empty', () => {
    const s = new SelectionState()
    expect(s.size).toBe(0)
    expect(s.has('x')).toBe(false)
  })

  it('set/add/remove/toggle/clear all fire listeners', () => {
    const s = new SelectionState()
    const fn = vi.fn()
    s.subscribe(fn)

    s.set(['a', 'b'])
    expect(s.size).toBe(2)
    expect(fn).toHaveBeenCalledTimes(1)

    s.add('c')
    expect(s.size).toBe(3)
    expect(fn).toHaveBeenCalledTimes(2)

    s.toggle('c')
    expect(s.has('c')).toBe(false)
    expect(fn).toHaveBeenCalledTimes(3)

    s.toggle('c')
    expect(s.has('c')).toBe(true)
    expect(fn).toHaveBeenCalledTimes(4)

    s.remove('a')
    expect(s.size).toBe(2)
    expect(fn).toHaveBeenCalledTimes(5)

    s.clear()
    expect(s.size).toBe(0)
    expect(fn).toHaveBeenCalledTimes(6)
  })

  it('add/remove/clear are no-ops when nothing changes', () => {
    const s = new SelectionState()
    const fn = vi.fn()
    s.subscribe(fn)

    s.add('a')
    s.add('a') // already selected
    expect(fn).toHaveBeenCalledTimes(1)

    s.remove('b') // not selected
    expect(fn).toHaveBeenCalledTimes(1)

    s.clear() // still holding 'a' — fires
    expect(fn).toHaveBeenCalledTimes(2)
    s.clear() // already empty — no-op
    expect(fn).toHaveBeenCalledTimes(2)
  })

  it('reconcile drops ids absent from the provided set', () => {
    const s = new SelectionState()
    s.set(['a', 'b', 'c'])
    const fn = vi.fn()
    s.subscribe(fn)

    const changed = s.reconcile(new Set(['a', 'c', 'd']))
    expect(changed).toBe(true)
    expect(Array.from(s.snapshot).sort()).toEqual(['a', 'c'])
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('reconcile returns false and does not emit when nothing was dropped', () => {
    const s = new SelectionState()
    s.set(['a', 'b'])
    const fn = vi.fn()
    s.subscribe(fn)

    const changed = s.reconcile(new Set(['a', 'b', 'c']))
    expect(changed).toBe(false)
    expect(fn).not.toHaveBeenCalled()
  })

  it('subscribe returns a disposer', () => {
    const s = new SelectionState()
    const fn = vi.fn()
    const off = s.subscribe(fn)
    s.add('a')
    expect(fn).toHaveBeenCalledTimes(1)
    off()
    s.add('b')
    expect(fn).toHaveBeenCalledTimes(1)
  })
})
