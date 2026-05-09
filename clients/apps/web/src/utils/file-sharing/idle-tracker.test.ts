import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { IdleTracker } from './idle-tracker'

describe('IdleTracker', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('fires onIdle once when the idle timeout elapses without activity', () => {
    const onIdle = vi.fn()
    const t = new IdleTracker(60_000, onIdle, undefined, 1_000)
    // Advance past the idle threshold — the interval fires every 1s,
    // and the check compares Date.now() - lastActivity > 60s.
    vi.advanceTimersByTime(61_000)
    expect(onIdle).toHaveBeenCalledTimes(1)
    // After firing, destroy() clears the interval so it cannot fire
    // again even if more time passes.
    vi.advanceTimersByTime(120_000)
    expect(onIdle).toHaveBeenCalledTimes(1)
    t.destroy()
  })

  it('does not fire when activity resets inside the timeout window', () => {
    const onIdle = vi.fn()
    const t = new IdleTracker(60_000, onIdle, undefined, 1_000)
    vi.advanceTimersByTime(30_000)
    t.resetActivity()
    vi.advanceTimersByTime(30_000)
    t.resetActivity()
    vi.advanceTimersByTime(30_000)
    expect(onIdle).not.toHaveBeenCalled()
    t.destroy()
  })

  it('schedules the first ping at interval/2, then repeats at interval', () => {
    const onIdle = vi.fn()
    const onPing = vi.fn()
    const t = new IdleTracker(60_000, onIdle, onPing, 1_000)
    // The first ping fires after interval/2 = 500ms.
    vi.advanceTimersByTime(499)
    expect(onPing).not.toHaveBeenCalled()
    vi.advanceTimersByTime(1)
    expect(onPing).toHaveBeenCalledTimes(1)
    // Subsequent pings every 1_000ms.
    vi.advanceTimersByTime(1_000)
    expect(onPing).toHaveBeenCalledTimes(2)
    vi.advanceTimersByTime(1_000)
    expect(onPing).toHaveBeenCalledTimes(3)
    t.destroy()
  })

  it('destroy() stops all timers', () => {
    const onIdle = vi.fn()
    const onPing = vi.fn()
    const t = new IdleTracker(60_000, onIdle, onPing, 1_000)
    t.destroy()
    vi.advanceTimersByTime(120_000)
    expect(onIdle).not.toHaveBeenCalled()
    expect(onPing).not.toHaveBeenCalled()
  })

  it('destroy() before the first ping-start timeout cancels the ping chain', () => {
    const onPing = vi.fn()
    const t = new IdleTracker(60_000, vi.fn(), onPing, 1_000)
    // Destroy before interval/2 elapses (the ping-start timeout hasn't
    // run yet). No pings should fire.
    vi.advanceTimersByTime(100)
    t.destroy()
    vi.advanceTimersByTime(5_000)
    expect(onPing).not.toHaveBeenCalled()
  })

  it('calls destroy() before onIdle so re-entrant handlers are safe', () => {
    // If the onIdle handler tries to do work with the tracker, the
    // internal timers are already cleared. Easiest observable check:
    // advancing time inside the handler doesn't re-fire onIdle.
    const order: string[] = []
    const onIdle = vi.fn(() => {
      order.push('idle')
      vi.advanceTimersByTime(120_000)
    })
    const t = new IdleTracker(60_000, onIdle, undefined, 1_000)
    vi.advanceTimersByTime(61_000)
    expect(onIdle).toHaveBeenCalledTimes(1)
    expect(order).toEqual(['idle'])
    t.destroy()
  })

  it('does not schedule pings when onPing is not supplied', () => {
    const onIdle = vi.fn()
    const t = new IdleTracker(60_000, onIdle, undefined, 1_000)
    // Nothing to assert about pings (no handler), but time advancement
    // should not throw and should not fire onIdle prematurely.
    expect(() => vi.advanceTimersByTime(30_000)).not.toThrow()
    expect(onIdle).not.toHaveBeenCalled()
    t.destroy()
  })
})
