import { describe, expect, it } from 'vitest'

import { formatDimension, parseDimension } from './transform-input'

describe('parseDimension', () => {
  it('parses a plain integer', () => {
    expect(parseDimension('42')).toBe(42)
  })

  it('parses a negative number', () => {
    expect(parseDimension('-12.5')).toBe(-12.5)
  })

  it('parses decimals with dot', () => {
    expect(parseDimension('1.5')).toBe(1.5)
  })

  it('parses decimals with comma (locale tolerance)', () => {
    expect(parseDimension('1,5')).toBe(1.5)
  })

  it('trims surrounding whitespace', () => {
    expect(parseDimension('   3   ')).toBe(3)
  })

  it('accepts a leading +', () => {
    expect(parseDimension('+10')).toBe(10)
  })

  it('returns null for empty / whitespace input', () => {
    expect(parseDimension('')).toBeNull()
    expect(parseDimension('   ')).toBeNull()
  })

  it('returns null for non-numeric input', () => {
    expect(parseDimension('abc')).toBeNull()
    expect(parseDimension('12px')).toBeNull()
  })

  it('returns null for Infinity / NaN', () => {
    expect(parseDimension('Infinity')).toBeNull()
    expect(parseDimension('-Infinity')).toBeNull()
    expect(parseDimension('NaN')).toBeNull()
  })

  it('rejects values below min', () => {
    expect(parseDimension('0', { min: 1 })).toBeNull()
    expect(parseDimension('1', { min: 1 })).toBe(1)
  })

  it('rejects values above max', () => {
    expect(parseDimension('100', { max: 50 })).toBeNull()
    expect(parseDimension('50', { max: 50 })).toBe(50)
  })

  it('respects both bounds at once', () => {
    expect(parseDimension('5', { min: 0, max: 10 })).toBe(5)
    expect(parseDimension('-1', { min: 0, max: 10 })).toBeNull()
    expect(parseDimension('11', { min: 0, max: 10 })).toBeNull()
  })

  it('returns null for non-string input', () => {
    expect(parseDimension(42 as unknown as string)).toBeNull()
    expect(parseDimension(null as unknown as string)).toBeNull()
  })
})

describe('formatDimension', () => {
  it('formats an integer without trailing zeros', () => {
    expect(formatDimension(10)).toBe('10')
  })

  it('formats a decimal trimmed to the supplied precision', () => {
    expect(formatDimension(1.234, 2)).toBe('1.23')
    expect(formatDimension(1.235, 2)).toBe('1.24') // banker-style? toFixed
  })

  it('drops trailing zeros (10.50 → 10.5)', () => {
    expect(formatDimension(10.5, 2)).toBe('10.5')
    expect(formatDimension(10.0, 2)).toBe('10')
  })

  it('returns empty string for null / undefined / NaN', () => {
    expect(formatDimension(null)).toBe('')
    expect(formatDimension(undefined)).toBe('')
    expect(formatDimension(Number.NaN)).toBe('')
  })

  it('returns empty string for Infinity', () => {
    expect(formatDimension(Number.POSITIVE_INFINITY)).toBe('')
    expect(formatDimension(Number.NEGATIVE_INFINITY)).toBe('')
  })
})
