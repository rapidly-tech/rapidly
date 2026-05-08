import { describe, expect, it } from 'vitest'

import { digitToOpacity } from './opacity-quickkey'

describe('digitToOpacity', () => {
  it('maps 1..9 to 10..90 in tens', () => {
    for (let d = 1; d <= 9; d++) {
      expect(digitToOpacity(String(d))).toBe(d * 10)
    }
  })

  it('maps 0 to 100 (Figma — pressing 0 reads as "max")', () => {
    expect(digitToOpacity('0')).toBe(100)
  })

  it('returns null for non-digit single chars', () => {
    expect(digitToOpacity('a')).toBeNull()
    expect(digitToOpacity('!')).toBeNull()
    expect(digitToOpacity(' ')).toBeNull()
  })

  it('returns null for multi-char strings', () => {
    expect(digitToOpacity('12')).toBeNull()
    expect(digitToOpacity('')).toBeNull()
  })

  it('returns null for non-string input', () => {
    expect(digitToOpacity(5 as unknown as string)).toBeNull()
    expect(digitToOpacity(null as unknown as string)).toBeNull()
  })
})
