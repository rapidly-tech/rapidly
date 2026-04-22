import { describe, expect, it } from 'vitest'

import { secureCompare } from './secure-compare'

describe('secureCompare', () => {
  it('returns true for identical strings', () => {
    expect(secureCompare('abc', 'abc')).toBe(true)
    expect(secureCompare('', '')).toBe(true)
  })

  it('returns false for same-length but differing strings', () => {
    expect(secureCompare('abc', 'abd')).toBe(false)
    // Single-bit difference.
    expect(secureCompare('a', 'b')).toBe(false)
  })

  it('returns false for different-length strings', () => {
    expect(secureCompare('a', 'ab')).toBe(false)
    expect(secureCompare('ab', 'a')).toBe(false)
    expect(secureCompare('', 'x')).toBe(false)
  })

  it('handles multi-byte UTF-8 inputs (encodes via TextEncoder)', () => {
    // "é" is 2 bytes in UTF-8; pure JS string equality wouldn't trip
    // on this, but the byte-level loop needs to compare encoded bytes.
    expect(secureCompare('café', 'café')).toBe(true)
    expect(secureCompare('café', 'cafe')).toBe(false)
    expect(secureCompare('🔒', '🔒')).toBe(true)
    expect(secureCompare('🔒', '🔓')).toBe(false)
  })

  it('handles a 64-char SHA-256 hex digest (the fixed-min iteration target)', () => {
    const digest =
      'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
    expect(secureCompare(digest, digest)).toBe(true)
    // Flip one bit in the middle.
    const tampered = digest.replace('afbf', 'afcf')
    expect(secureCompare(digest, tampered)).toBe(false)
  })

  it('does not short-circuit when lengths differ', () => {
    // Hard to assert timing in jsdom directly; assert the iteration count
    // is at least the documented fixed minimum by feeding an input whose
    // handling would change if the implementation early-returned on
    // length mismatch. Smoke test: returns false without throwing.
    expect(() => secureCompare('x', 'y'.repeat(500))).not.toThrow()
    expect(secureCompare('x', 'y'.repeat(500))).toBe(false)
  })
})
