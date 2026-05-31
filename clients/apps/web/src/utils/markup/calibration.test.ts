import { describe, expect, it } from 'vitest'

import {
  computeBoardScale,
  pixelLength,
  type CalibrationLine,
} from './calibration'

describe('pixelLength', () => {
  it('returns euclidean distance for a horizontal line', () => {
    const line: CalibrationLine = { x1: 0, y1: 0, x2: 100, y2: 0 }
    expect(pixelLength(line)).toBe(100)
  })

  it('returns euclidean distance for a diagonal line', () => {
    const line: CalibrationLine = { x1: 0, y1: 0, x2: 3, y2: 4 }
    expect(pixelLength(line)).toBe(5)
  })

  it('handles reversed endpoints', () => {
    // Direction shouldn't matter for length.
    const a: CalibrationLine = { x1: 0, y1: 0, x2: 10, y2: 0 }
    const b: CalibrationLine = { x1: 10, y1: 0, x2: 0, y2: 0 }
    expect(pixelLength(a)).toBe(pixelLength(b))
  })

  it('handles negative coordinates', () => {
    const line: CalibrationLine = { x1: -5, y1: -5, x2: 5, y2: 5 }
    // sqrt(10^2 + 10^2) = sqrt(200) ≈ 14.142
    expect(pixelLength(line)).toBeCloseTo(Math.sqrt(200), 6)
  })
})

describe('computeBoardScale', () => {
  it('computes units-per-pixel from a calibration line + real length', () => {
    // A 100-pixel line that the user says is 5000 mm long → each
    // pixel represents 50 mm.
    const line: CalibrationLine = { x1: 0, y1: 0, x2: 100, y2: 0 }
    const scale = computeBoardScale(line, 5000, 'mm')
    expect(scale).not.toBeNull()
    expect(scale!.unitsPerPixel).toBe(50)
    expect(scale!.unit).toBe('mm')
  })

  it('preserves the unit choice on the returned scale', () => {
    const line: CalibrationLine = { x1: 0, y1: 0, x2: 200, y2: 0 }
    expect(computeBoardScale(line, 5, 'm')?.unit).toBe('m')
    expect(computeBoardScale(line, 5, 'in')?.unit).toBe('in')
    expect(computeBoardScale(line, 5, 'ft')?.unit).toBe('ft')
  })

  it('returns null when the line has zero length', () => {
    const line: CalibrationLine = { x1: 5, y1: 5, x2: 5, y2: 5 }
    expect(computeBoardScale(line, 10, 'm')).toBeNull()
  })

  it('returns null when the real length is non-positive', () => {
    const line: CalibrationLine = { x1: 0, y1: 0, x2: 100, y2: 0 }
    expect(computeBoardScale(line, 0, 'm')).toBeNull()
    expect(computeBoardScale(line, -5, 'm')).toBeNull()
  })
})
