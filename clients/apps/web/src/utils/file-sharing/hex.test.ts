import { describe, expect, it } from 'vitest'

import { toHex } from './hex'

describe('toHex', () => {
  it('returns an empty string for an empty input', () => {
    expect(toHex(new Uint8Array(0))).toBe('')
  })

  it('encodes low-value bytes with a leading zero', () => {
    expect(toHex(new Uint8Array([0, 1, 15, 16]))).toBe('00010f10')
  })

  it('encodes 0xff as "ff" (lowercase)', () => {
    expect(toHex(new Uint8Array([0xff]))).toBe('ff')
    expect(toHex(new Uint8Array([0xde, 0xad, 0xbe, 0xef]))).toBe('deadbeef')
  })

  it('always produces lowercase hex', () => {
    const bytes = new Uint8Array([0xab, 0xcd, 0xef])
    expect(toHex(bytes)).toBe('abcdef')
    expect(toHex(bytes)).toBe(toHex(bytes).toLowerCase())
  })

  it('produces a string exactly 2x the input length', () => {
    for (const n of [0, 1, 16, 32, 64, 128]) {
      const bytes = new Uint8Array(n)
      expect(toHex(bytes).length).toBe(n * 2)
    }
  })

  it('round-trips through the canonical decoder', () => {
    const original = new Uint8Array([
      0x01, 0x23, 0x45, 0x67, 0x89, 0xab, 0xcd, 0xef,
    ])
    const hex = toHex(original)
    expect(hex).toBe('0123456789abcdef')
    // Manual inverse: pair up nybbles.
    const decoded = new Uint8Array(
      hex.match(/.{2}/g)!.map((h) => parseInt(h, 16)),
    )
    expect(Array.from(decoded)).toEqual(Array.from(original))
  })
})
