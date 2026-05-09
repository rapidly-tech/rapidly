import { describe, expect, it } from 'vitest'

import {
  readReportedPressure,
  simulatePressureFromVelocity,
  smoothPressure,
} from './pressure'

describe('readReportedPressure', () => {
  it('returns null for mouse pointers regardless of pressure value', () => {
    expect(
      readReportedPressure({ pointerType: 'mouse', pressure: 0.5 }),
    ).toBeNull()
    expect(
      readReportedPressure({ pointerType: 'mouse', pressure: 1 }),
    ).toBeNull()
  })

  it('returns null for touch pointers', () => {
    expect(
      readReportedPressure({ pointerType: 'touch', pressure: 0.8 }),
    ).toBeNull()
  })

  it('returns null for pen with zero / negative / non-finite pressure', () => {
    expect(readReportedPressure({ pointerType: 'pen', pressure: 0 })).toBeNull()
    expect(
      readReportedPressure({ pointerType: 'pen', pressure: -0.5 }),
    ).toBeNull()
    expect(
      readReportedPressure({ pointerType: 'pen', pressure: NaN }),
    ).toBeNull()
    expect(readReportedPressure({ pointerType: 'pen' })).toBeNull()
  })

  it('returns the pen pressure clamped to [0, 1]', () => {
    expect(
      readReportedPressure({ pointerType: 'pen', pressure: 0.7 }),
    ).toBeCloseTo(0.7, 10)
    expect(readReportedPressure({ pointerType: 'pen', pressure: 2 })).toBe(1)
  })

  it('returns null when pointerType is missing', () => {
    expect(readReportedPressure({ pressure: 0.5 })).toBeNull()
  })
})

describe('simulatePressureFromVelocity', () => {
  it('zero time delta falls back to slow pressure', () => {
    const p = simulatePressureFromVelocity(
      { x: 0, y: 0, t: 100 },
      { x: 10, y: 0, t: 100 },
    )
    expect(p).toBe(0.9) // default slow
  })

  it('stationary (zero distance) → slow pressure', () => {
    const p = simulatePressureFromVelocity(
      { x: 5, y: 5, t: 0 },
      { x: 5, y: 5, t: 100 },
    )
    expect(p).toBe(0.9)
  })

  it('fast strokes saturate at fastPressure', () => {
    // 100 px in 10 ms = 10 px/ms — well past the 2 px/ms fast
    // endpoint.
    const p = simulatePressureFromVelocity(
      { x: 0, y: 0, t: 0 },
      { x: 100, y: 0, t: 10 },
    )
    expect(p).toBe(0.2) // default fast
  })

  it('linearly interpolates between slow and fast at intermediate velocity', () => {
    // 1 px/ms, exactly halfway between 0 and the 2 px/ms fast
    // endpoint. Result should sit at the midpoint of slow (0.9) and
    // fast (0.2) = 0.55.
    const p = simulatePressureFromVelocity(
      { x: 0, y: 0, t: 0 },
      { x: 10, y: 0, t: 10 },
    )
    expect(p).toBeCloseTo(0.55, 5)
  })

  it('respects custom slow / fast / fastVelocity options', () => {
    const p = simulatePressureFromVelocity(
      { x: 0, y: 0, t: 0 },
      { x: 1, y: 0, t: 1 },
      { slowPressure: 1, fastPressure: 0, fastVelocityPxPerMs: 4 },
    )
    // 1 px/ms / 4 px/ms = 0.25; slow=1, fast=0 → 1 + (0-1)*0.25 = 0.75.
    expect(p).toBeCloseTo(0.75, 5)
  })

  it('never returns a value outside [fast, slow]', () => {
    // Slow + fast intentionally flipped — helper still clamps at the
    // endpoints so downstream consumers can't get a surprise value.
    const slowP = simulatePressureFromVelocity(
      { x: 0, y: 0, t: 0 },
      { x: 0, y: 0, t: 10 },
    )
    expect(slowP).toBe(0.9)
    const fastP = simulatePressureFromVelocity(
      { x: 0, y: 0, t: 0 },
      { x: 1000, y: 0, t: 1 },
    )
    expect(fastP).toBe(0.2)
  })
})

describe('smoothPressure', () => {
  it('alpha = 1 returns target (no smoothing)', () => {
    expect(smoothPressure(0.2, 0.8, 1)).toBe(0.8)
  })

  it('alpha = 0 returns current (full smoothing)', () => {
    expect(smoothPressure(0.2, 0.8, 0)).toBe(0.2)
  })

  it('alpha = 0.5 returns midpoint', () => {
    expect(smoothPressure(0.2, 0.8, 0.5)).toBeCloseTo(0.5, 5)
  })

  it('default alpha (0.4) weights the new sample less than current', () => {
    // 0.2 * 0.6 + 0.8 * 0.4 = 0.12 + 0.32 = 0.44.
    expect(smoothPressure(0.2, 0.8)).toBeCloseTo(0.44, 5)
  })

  it('clamps alpha outside [0, 1]', () => {
    expect(smoothPressure(0.2, 0.8, -1)).toBe(0.2)
    expect(smoothPressure(0.2, 0.8, 2)).toBe(0.8)
  })
})
