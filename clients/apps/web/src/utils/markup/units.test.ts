import { describe, expect, it } from 'vitest'

import type { BoardScale } from './calibration'
import { makeFormatter } from './units'

describe('makeFormatter (no scale)', () => {
  it('falls back to whole-pixel rendering when scale is null', () => {
    const f = makeFormatter(null)
    expect(f.format(400)).toBe('400 px')
  })

  it('rounds non-integer pixel values', () => {
    const f = makeFormatter(null)
    expect(f.format(400.3)).toBe('400 px')
    expect(f.format(400.7)).toBe('401 px')
  })
})

describe('makeFormatter (mm)', () => {
  // 1 px = 50 mm — what we get from calibrating a 100-px line as 5000 mm.
  const scale: BoardScale = { unitsPerPixel: 50, unit: 'mm' }

  it('renders mm with 0 decimals', () => {
    const f = makeFormatter(scale)
    expect(f.format(10)).toBe('500 mm')
    expect(f.format(100)).toBe('5000 mm')
  })
})

describe('makeFormatter (m)', () => {
  // 1 px = 0.05 m
  const scale: BoardScale = { unitsPerPixel: 0.05, unit: 'm' }

  it('renders m with 2 decimals', () => {
    const f = makeFormatter(scale)
    expect(f.format(100)).toBe('5.00 m')
    expect(f.format(123)).toBe('6.15 m')
  })
})

describe('makeFormatter (in)', () => {
  // 1 px = 0.25 inch
  const scale: BoardScale = { unitsPerPixel: 0.25, unit: 'in' }

  it('renders in with 2 decimals', () => {
    const f = makeFormatter(scale)
    expect(f.format(4)).toBe('1.00 in')
    expect(f.format(10)).toBe('2.50 in')
  })
})

describe('makeFormatter (ft)', () => {
  // 1 px = 0.1 ft
  const scale: BoardScale = { unitsPerPixel: 0.1, unit: 'ft' }

  it('renders ft with 1 decimal (decimal feet, not arch ft-in)', () => {
    const f = makeFormatter(scale)
    expect(f.format(50)).toBe('5.0 ft')
    expect(f.format(53)).toBe('5.3 ft')
  })
})
