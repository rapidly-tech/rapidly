import { beforeEach, describe, expect, it, vi } from 'vitest'

import { _resetEditBroker, onEditRequest, requestEdit } from './text-editing'

describe('text-editing broker', () => {
  beforeEach(() => {
    _resetEditBroker()
  })

  it('notifies subscribers on requestEdit', () => {
    const fn = vi.fn()
    onEditRequest(fn)
    requestEdit('abc')
    expect(fn).toHaveBeenCalledWith('abc')
  })

  it('fires the current state once when a subscriber attaches late', () => {
    requestEdit('abc')
    const fn = vi.fn()
    onEditRequest(fn)
    expect(fn).toHaveBeenCalledWith('abc')
  })

  it('does NOT replay to late subscribers when state is null', () => {
    const fn = vi.fn()
    onEditRequest(fn)
    expect(fn).not.toHaveBeenCalled()
  })

  it('cancels via requestEdit(null)', () => {
    const fn = vi.fn()
    onEditRequest(fn)
    requestEdit('abc')
    requestEdit(null)
    expect(fn).toHaveBeenLastCalledWith(null)
  })

  it('subscribe returns a disposer', () => {
    const fn = vi.fn()
    const off = onEditRequest(fn)
    requestEdit('abc')
    expect(fn).toHaveBeenCalledTimes(1)
    off()
    requestEdit('xyz')
    expect(fn).toHaveBeenCalledTimes(1)
  })
})
