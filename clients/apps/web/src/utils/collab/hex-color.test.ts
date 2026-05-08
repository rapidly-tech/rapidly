import { describe, expect, it } from 'vitest'

import { isValidHex, normaliseHex } from './hex-color'

describe('normaliseHex', () => {
  it('canonicalises a 6-digit hex with hash', () => {
    expect(normaliseHex('#a5d8ff')).toBe('#a5d8ff')
  })

  it('lowercases mixed case input', () => {
    expect(normaliseHex('#A5D8Ff')).toBe('#a5d8ff')
  })

  it('adds the leading hash when missing', () => {
    expect(normaliseHex('a5d8ff')).toBe('#a5d8ff')
  })

  it('expands 3-digit shorthand to 6 digits', () => {
    expect(normaliseHex('#abc')).toBe('#aabbcc')
    expect(normaliseHex('abc')).toBe('#aabbcc')
  })

  it('trims surrounding whitespace', () => {
    expect(normaliseHex('   #abc   ')).toBe('#aabbcc')
  })

  it('returns null for empty / whitespace-only input', () => {
    expect(normaliseHex('')).toBeNull()
    expect(normaliseHex('   ')).toBeNull()
  })

  it('returns null for non-hex characters', () => {
    expect(normaliseHex('#xyz123')).toBeNull()
    expect(normaliseHex('rgb(255,0,0)')).toBeNull()
  })

  it('returns null for non-3 / non-6 lengths', () => {
    expect(normaliseHex('#a')).toBeNull()
    expect(normaliseHex('#ab')).toBeNull()
    expect(normaliseHex('#abcd')).toBeNull()
    expect(normaliseHex('#abcde')).toBeNull()
    expect(normaliseHex('#abcdefa')).toBeNull()
  })

  it('rejects 8-digit rrggbbaa (alpha not supported)', () => {
    expect(normaliseHex('#aabbccdd')).toBeNull()
  })

  it('returns null for non-string input', () => {
    expect(normaliseHex(null as unknown as string)).toBeNull()
    expect(normaliseHex(123 as unknown as string)).toBeNull()
  })
})

describe('isValidHex', () => {
  it('mirrors normaliseHex non-null', () => {
    expect(isValidHex('#a5d8ff')).toBe(true)
    expect(isValidHex('a5d8ff')).toBe(true)
    expect(isValidHex('#abc')).toBe(true)
    expect(isValidHex('not-a-colour')).toBe(false)
    expect(isValidHex('')).toBe(false)
  })
})
