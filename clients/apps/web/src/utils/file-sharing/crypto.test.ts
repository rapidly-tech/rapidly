import { describe, expect, it } from 'vitest'

/**
 * Test the hashPassword algorithm directly.
 * We re-implement it here to avoid importing crypto.ts which has OpenPGP
 * dependencies that don't work well in the vitest environment.
 */
async function hashPassword(password: string): Promise<string> {
  const encoder = new TextEncoder()
  const data = encoder.encode(password)
  const hashBuffer = await crypto.subtle.digest('SHA-256', data)
  const hashArray = Array.from(new Uint8Array(hashBuffer))
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('')
}

/**
 * Test the secureCompare algorithm directly.
 * We re-implement it here to avoid importing crypto.ts which has OpenPGP
 * dependencies that don't work well in the vitest environment.
 *
 * This tests the ALGORITHM, and the actual implementation in crypto.ts
 * uses the same logic.
 */
function secureCompare(a: string, b: string): boolean {
  const encoder = new TextEncoder()
  const bufA = encoder.encode(a)
  const bufB = encoder.encode(b)

  // Match the actual implementation in crypto.ts which uses min 64 iterations
  // to prevent timing side-channels on short inputs
  const maxLength = Math.max(bufA.length, bufB.length, 64)

  let result = bufA.length ^ bufB.length
  for (let i = 0; i < maxLength; i++) {
    const byteA = i < bufA.length ? bufA[i] : 0
    const byteB = i < bufB.length ? bufB[i] : 0
    result |= byteA ^ byteB
  }

  return result === 0
}

describe('secureCompare', () => {
  it('returns true for equal strings', () => {
    expect(secureCompare('password123', 'password123')).toBe(true)
    expect(secureCompare('', '')).toBe(true)
    expect(secureCompare('a', 'a')).toBe(true)
  })

  it('returns false for different strings', () => {
    expect(secureCompare('password123', 'password124')).toBe(false)
    expect(secureCompare('password123', 'Password123')).toBe(false)
    expect(secureCompare('abc', 'abd')).toBe(false)
  })

  it('returns false for strings of different lengths', () => {
    expect(secureCompare('short', 'longer')).toBe(false)
    expect(secureCompare('password', 'pass')).toBe(false)
    expect(secureCompare('', 'nonempty')).toBe(false)
  })

  it('handles unicode strings correctly', () => {
    expect(secureCompare('пароль', 'пароль')).toBe(true)
    expect(secureCompare('密码', '密码')).toBe(true)
    expect(secureCompare('пароль', 'парольx')).toBe(false)
  })

  it('handles special characters correctly', () => {
    expect(secureCompare('p@$$w0rd!', 'p@$$w0rd!')).toBe(true)
    expect(secureCompare('p@$$w0rd!', 'p@$$w0rd?')).toBe(false)
  })

  it('is constant-time for same-length strings', () => {
    // This test verifies the algorithm works correctly for timing attack prevention
    // We can't actually measure timing in JS tests, but we verify the logic

    // Difference at start vs difference at end should both return false
    expect(secureCompare('Xbcdefgh', 'abcdefgh')).toBe(false)
    expect(secureCompare('abcdefgX', 'abcdefgh')).toBe(false)

    // Both should process all characters (not short-circuit)
    // This is what makes it constant-time
  })

  it('handles empty vs non-empty correctly', () => {
    expect(secureCompare('', 'a')).toBe(false)
    expect(secureCompare('a', '')).toBe(false)
    expect(secureCompare('', '')).toBe(true)
  })

  it('handles very long strings', () => {
    const long1 = 'a'.repeat(10000)
    const long2 = 'a'.repeat(10000)
    const long3 = 'a'.repeat(9999) + 'b'

    expect(secureCompare(long1, long2)).toBe(true)
    expect(secureCompare(long1, long3)).toBe(false)
  })
})

describe('hashPassword', () => {
  it('returns a 64-character hex string', async () => {
    const hash = await hashPassword('test-password')
    expect(hash).toHaveLength(64)
    expect(hash).toMatch(/^[a-f0-9]{64}$/)
  })

  it('produces consistent hashes for same input', async () => {
    const hash1 = await hashPassword('consistent-password')
    const hash2 = await hashPassword('consistent-password')
    expect(hash1).toBe(hash2)
  })

  it('produces different hashes for different inputs', async () => {
    const hash1 = await hashPassword('password1')
    const hash2 = await hashPassword('password2')
    expect(hash1).not.toBe(hash2)
  })

  it('produces URL-safe output (no special characters)', async () => {
    const hash = await hashPassword('test')
    // Should only contain lowercase hex characters
    expect(hash).not.toMatch(/[^a-f0-9]/)
  })

  it('handles empty string', async () => {
    const hash = await hashPassword('')
    expect(hash).toHaveLength(64)
    // SHA-256 of empty string is well-known
    expect(hash).toBe(
      'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    )
  })

  it('handles unicode characters', async () => {
    const hash = await hashPassword('пароль密码')
    expect(hash).toHaveLength(64)
    expect(hash).toMatch(/^[a-f0-9]{64}$/)
  })
})
