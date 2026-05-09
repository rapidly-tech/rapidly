import { describe, expect, it } from 'vitest'

import { createPinchPanGesture } from './pinch-gesture'

describe('createPinchPanGesture', () => {
  it('starts inactive', () => {
    const g = createPinchPanGesture()
    expect(g.active()).toBe(false)
  })

  it('one pointer down is not enough to activate', () => {
    const g = createPinchPanGesture()
    g.onPointerDown({ id: 1, x: 0, y: 0 })
    expect(g.active()).toBe(false)
    expect(g.onPointerMove({ id: 1, x: 10, y: 10 })).toBeNull()
  })

  it('two pointers down activates the gesture', () => {
    const g = createPinchPanGesture()
    g.onPointerDown({ id: 1, x: 0, y: 0 })
    g.onPointerDown({ id: 2, x: 100, y: 0 })
    expect(g.active()).toBe(true)
  })

  it('moving one pointer apart produces a scaleFactor > 1', () => {
    const g = createPinchPanGesture()
    g.onPointerDown({ id: 1, x: 0, y: 0 })
    g.onPointerDown({ id: 2, x: 100, y: 0 })
    // Pull pointer 2 twice as far — distance goes 100 → 200.
    const update = g.onPointerMove({ id: 2, x: 200, y: 0 })
    expect(update).not.toBeNull()
    expect(update!.scaleFactor).toBeCloseTo(2, 5)
  })

  it('scaleFactor is the delta vs the previous move, not vs start', () => {
    const g = createPinchPanGesture()
    g.onPointerDown({ id: 1, x: 0, y: 0 })
    g.onPointerDown({ id: 2, x: 100, y: 0 })
    // First move: 100 → 150 → scaleFactor 1.5.
    const a = g.onPointerMove({ id: 2, x: 150, y: 0 })!
    expect(a.scaleFactor).toBeCloseTo(1.5, 5)
    // Second move: 150 → 300 → scaleFactor 2 (incremental).
    const b = g.onPointerMove({ id: 2, x: 300, y: 0 })!
    expect(b.scaleFactor).toBeCloseTo(2, 5)
  })

  it('midpoint shift produces pan deltas', () => {
    const g = createPinchPanGesture()
    g.onPointerDown({ id: 1, x: 0, y: 0 })
    g.onPointerDown({ id: 2, x: 100, y: 0 })
    // Midpoint starts at (50, 0). Move one pointer so midpoint shifts
    // to (75, 25) — pan delta should be (25, 25).
    const a = g.onPointerMove({ id: 1, x: 50, y: 50 })!
    expect(a.panDeltaScreenX).toBeCloseTo(25)
    expect(a.panDeltaScreenY).toBeCloseTo(25)
  })

  it('center tracks the current pinch midpoint', () => {
    const g = createPinchPanGesture()
    g.onPointerDown({ id: 1, x: 0, y: 0 })
    g.onPointerDown({ id: 2, x: 100, y: 0 })
    const update = g.onPointerMove({ id: 1, x: 50, y: 80 })!
    expect(update.centerScreenX).toBeCloseTo(75)
    expect(update.centerScreenY).toBeCloseTo(40)
  })

  it('a third pointer is ignored while two are tracked', () => {
    const g = createPinchPanGesture()
    g.onPointerDown({ id: 1, x: 0, y: 0 })
    g.onPointerDown({ id: 2, x: 100, y: 0 })
    g.onPointerDown({ id: 3, x: 500, y: 500 })
    // Moving the ignored pointer returns null.
    expect(g.onPointerMove({ id: 3, x: 800, y: 800 })).toBeNull()
    // The tracked pair still produces updates.
    expect(g.onPointerMove({ id: 1, x: 10, y: 0 })).not.toBeNull()
  })

  it('any pointer leaving deactivates the gesture', () => {
    const g = createPinchPanGesture()
    g.onPointerDown({ id: 1, x: 0, y: 0 })
    g.onPointerDown({ id: 2, x: 100, y: 0 })
    g.onPointerUp(1)
    expect(g.active()).toBe(false)
    // Remaining pointer does not produce an update.
    expect(g.onPointerMove({ id: 2, x: 10, y: 10 })).toBeNull()
  })

  it('reset drops every pointer', () => {
    const g = createPinchPanGesture()
    g.onPointerDown({ id: 1, x: 0, y: 0 })
    g.onPointerDown({ id: 2, x: 100, y: 0 })
    g.reset()
    expect(g.active()).toBe(false)
    // The next pointerdown starts fresh — one is still not enough.
    g.onPointerDown({ id: 3, x: 0, y: 0 })
    expect(g.active()).toBe(false)
  })

  it('re-firing pointerdown for an existing id updates its position without double-tracking', () => {
    const g = createPinchPanGesture()
    g.onPointerDown({ id: 1, x: 0, y: 0 })
    g.onPointerDown({ id: 1, x: 10, y: 10 })
    // Still one tracked — not active yet.
    expect(g.active()).toBe(false)
    g.onPointerDown({ id: 2, x: 100, y: 0 })
    expect(g.active()).toBe(true)
  })

  it('zero-distance pinch does not divide by zero', () => {
    const g = createPinchPanGesture()
    g.onPointerDown({ id: 1, x: 50, y: 50 })
    g.onPointerDown({ id: 2, x: 50, y: 50 })
    const update = g.onPointerMove({ id: 1, x: 60, y: 50 })
    expect(update).not.toBeNull()
    expect(Number.isFinite(update!.scaleFactor)).toBe(true)
  })
})
