import { describe, expect, it } from 'vitest'

import { createSwipeDismiss } from './swipe-dismiss'

describe('createSwipeDismiss', () => {
  it('ignores moves before the first pointerdown', () => {
    const g = createSwipeDismiss()
    expect(g.onPointerMove(100, 0)).toBeNull()
  })

  it('tracks translateY as y - startY', () => {
    const g = createSwipeDismiss()
    g.onPointerDown(100, 0)
    expect(g.onPointerMove(150, 10)).toEqual({ translateY: 50 })
    expect(g.onPointerMove(200, 20)).toEqual({ translateY: 100 })
  })

  it('clamps translateY to ≥ 0 (no upward peel)', () => {
    const g = createSwipeDismiss()
    g.onPointerDown(100, 0)
    expect(g.onPointerMove(50, 10)).toEqual({ translateY: 0 })
  })

  it('dismisses when travel exceeds distance threshold', () => {
    const g = createSwipeDismiss({ distanceThresholdPx: 80 })
    g.onPointerDown(100, 0)
    g.onPointerMove(150, 50)
    const release = g.onPointerUp(200, 100)
    expect(release.dismiss).toBe(true)
    expect(release.translateY).toBe(100)
  })

  it('snaps back when travel is under threshold and velocity is slow', () => {
    const g = createSwipeDismiss({
      distanceThresholdPx: 80,
      velocityThresholdPxPerMs: 0.5,
    })
    g.onPointerDown(100, 0)
    g.onPointerMove(120, 100)
    g.onPointerMove(130, 200)
    const release = g.onPointerUp(135, 300)
    expect(release.dismiss).toBe(false)
    expect(release.translateY).toBe(35)
  })

  it('dismisses on a quick flick even when travel is small', () => {
    const g = createSwipeDismiss({
      distanceThresholdPx: 1000, // impossibly high so velocity must trigger
      velocityThresholdPxPerMs: 0.5,
    })
    g.onPointerDown(0, 0)
    g.onPointerMove(10, 10)
    // Sample jumps by 30 px in 20 ms → velocity 1.5 px/ms — well
    // past the 0.5 threshold.
    g.onPointerMove(40, 30)
    const release = g.onPointerUp(40, 30)
    expect(release.dismiss).toBe(true)
  })

  it('velocity uses the last two samples (not the gesture average)', () => {
    const g = createSwipeDismiss({
      distanceThresholdPx: 1000,
      velocityThresholdPxPerMs: 0.5,
    })
    g.onPointerDown(0, 0)
    // Slow initial drag — average velocity near zero.
    g.onPointerMove(5, 500)
    g.onPointerMove(5, 1000)
    // Then a flick on the last sample: 5 → 80 in 100 ms = 0.75 px/ms,
    // clearly over the 0.5 threshold.
    g.onPointerMove(80, 1100)
    const release = g.onPointerUp(80, 1100)
    expect(release.dismiss).toBe(true)
  })

  it('no-op release before any gesture started', () => {
    const g = createSwipeDismiss()
    expect(g.onPointerUp(100, 0)).toEqual({ dismiss: false, translateY: 0 })
  })

  it('onPointerDown is ignored while a gesture is already active', () => {
    const g = createSwipeDismiss()
    g.onPointerDown(100, 0)
    g.onPointerDown(500, 10) // should not reset origin
    expect(g.onPointerMove(150, 20)).toEqual({ translateY: 50 })
  })

  it('reset drops state so next move returns null', () => {
    const g = createSwipeDismiss()
    g.onPointerDown(100, 0)
    g.reset()
    expect(g.onPointerMove(150, 10)).toBeNull()
  })

  it('after a release, next pointerdown starts fresh', () => {
    const g = createSwipeDismiss()
    g.onPointerDown(100, 0)
    g.onPointerUp(200, 100)
    g.onPointerDown(50, 200)
    expect(g.onPointerMove(90, 210)).toEqual({ translateY: 40 })
  })
})
