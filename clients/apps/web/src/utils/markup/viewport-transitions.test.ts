import { describe, expect, it, vi } from 'vitest'

import { makeViewport } from './viewport'
import {
  animateViewport,
  easeInOutCubic,
  lerpViewport,
} from './viewport-transitions'

describe('easeInOutCubic', () => {
  it('anchors at 0 and 1', () => {
    expect(easeInOutCubic(0)).toBe(0)
    expect(easeInOutCubic(1)).toBe(1)
  })

  it('clamps out-of-range values', () => {
    expect(easeInOutCubic(-0.5)).toBe(0)
    expect(easeInOutCubic(1.5)).toBe(1)
  })

  it('midpoint is exactly 0.5', () => {
    expect(easeInOutCubic(0.5)).toBeCloseTo(0.5, 10)
  })

  it('is monotonically non-decreasing', () => {
    let prev = 0
    for (let t = 0; t <= 1; t += 0.05) {
      const v = easeInOutCubic(t)
      expect(v).toBeGreaterThanOrEqual(prev)
      prev = v
    }
  })
})

describe('lerpViewport', () => {
  const from = makeViewport({ scale: 1, scrollX: 0, scrollY: 0 })
  const to = makeViewport({ scale: 3, scrollX: 100, scrollY: 200 })

  it('returns start viewport at t=0', () => {
    const out = lerpViewport(from, to, 0)
    expect(out).toEqual({ scale: 1, scrollX: 0, scrollY: 0 })
  })

  it('returns end viewport at t=1', () => {
    const out = lerpViewport(from, to, 1)
    expect(out).toEqual({ scale: 3, scrollX: 100, scrollY: 200 })
  })

  it('eased midpoint is exactly the geometric midpoint', () => {
    // ease(0.5) = 0.5, so lerp(0.5) is (1+3)/2, (0+100)/2, (0+200)/2.
    const out = lerpViewport(from, to, 0.5)
    expect(out.scale).toBeCloseTo(2, 10)
    expect(out.scrollX).toBeCloseTo(50, 10)
    expect(out.scrollY).toBeCloseTo(100, 10)
  })

  it('clamps scale into the legal range on every frame', () => {
    // Animate to a wildly out-of-range scale. Every intermediate
    // viewport's scale must still be legal.
    const insane = makeViewport({ scale: 999, scrollX: 0, scrollY: 0 })
    for (let t = 0; t <= 1; t += 0.1) {
      const out = lerpViewport(from, insane, t)
      expect(out.scale).toBeLessThanOrEqual(30)
    }
  })
})

describe('animateViewport', () => {
  function fakeRaf() {
    const queue: Array<(t: number) => void> = []
    let now = 0
    let handle = 0
    const raf = (cb: (t: number) => void): number => {
      queue.push(cb)
      return ++handle
    }
    const caf = (_h: number): void => {
      queue.length = 0
    }
    const tick = (advanceMs: number): void => {
      now += advanceMs
      const batch = queue.splice(0)
      for (const cb of batch) cb(now)
    }
    return { raf, caf, tick, nowFn: () => now }
  }

  it('snaps immediately on zero duration and fires onFrame + onDone once', () => {
    const onFrame = vi.fn()
    const onDone = vi.fn()
    const { raf, caf, nowFn } = fakeRaf()
    const to = makeViewport({ scale: 2 })
    animateViewport(makeViewport(), to, {
      durationMs: 0,
      onFrame,
      onDone,
      requestFrame: raf,
      cancelFrame: caf,
      now: nowFn,
    })
    expect(onFrame).toHaveBeenCalledTimes(1)
    expect(onFrame.mock.calls[0][0]).toEqual(to)
    expect(onDone).toHaveBeenCalledWith(true)
  })

  it('animates frames over the duration and lands exactly on the target', () => {
    const onFrame = vi.fn()
    const onDone = vi.fn()
    const { raf, caf, tick, nowFn } = fakeRaf()
    const from = makeViewport()
    const to = makeViewport({ scale: 2, scrollX: 100, scrollY: 100 })
    animateViewport(from, to, {
      durationMs: 400,
      onFrame,
      onDone,
      requestFrame: raf,
      cancelFrame: caf,
      now: nowFn,
    })
    // First scheduled frame fires at t=0 ms — start of animation.
    tick(0)
    // Advance to mid-animation.
    tick(200)
    // Final frame at or past duration.
    tick(200)
    expect(onDone).toHaveBeenCalledWith(true)
    const lastCall = onFrame.mock.calls[onFrame.mock.calls.length - 1][0]
    expect(lastCall).toEqual(to)
  })

  it('cancel stops further frames and reports cancelled', () => {
    const onFrame = vi.fn()
    const onDone = vi.fn()
    const { raf, caf, tick, nowFn } = fakeRaf()
    const handle = animateViewport(makeViewport(), makeViewport({ scale: 3 }), {
      durationMs: 400,
      onFrame,
      onDone,
      requestFrame: raf,
      cancelFrame: caf,
      now: nowFn,
    })
    tick(0)
    const framesBefore = onFrame.mock.calls.length
    handle.cancel()
    tick(200)
    // No new frames after cancel.
    expect(onFrame.mock.calls.length).toBe(framesBefore)
    expect(onDone).toHaveBeenCalledWith(false)
  })

  it('double-cancel is a silent no-op', () => {
    const onDone = vi.fn()
    const { raf, caf, nowFn } = fakeRaf()
    const handle = animateViewport(makeViewport(), makeViewport(), {
      durationMs: 400,
      onFrame: () => {},
      onDone,
      requestFrame: raf,
      cancelFrame: caf,
      now: nowFn,
    })
    handle.cancel()
    handle.cancel()
    expect(onDone).toHaveBeenCalledTimes(1)
  })
})
