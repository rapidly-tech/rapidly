import { describe, expect, it } from 'vitest'
import {
  computeKeyCommitment,
  exportKey,
  generateMasterKey,
  generateSalt,
  importKey,
  verifyKeyCommitment,
} from './encryption'

describe('Key Commitment (HMAC-SHA256)', () => {
  it('produces a 64-char hex string', async () => {
    const key = await generateMasterKey()
    const salt = generateSalt()
    const commitment = await computeKeyCommitment(
      key,
      'test.txt',
      1024,
      0,
      salt,
    )
    expect(commitment).toHaveLength(64)
    expect(commitment).toMatch(/^[a-f0-9]{64}$/)
  })

  it('is deterministic for the same inputs', async () => {
    const key = await generateMasterKey()
    const salt = generateSalt()
    const c1 = await computeKeyCommitment(key, 'test.txt', 1024, 0, salt)
    const c2 = await computeKeyCommitment(key, 'test.txt', 1024, 0, salt)
    expect(c1).toBe(c2)
  })

  it('changes when fileName differs', async () => {
    const key = await generateMasterKey()
    const salt = generateSalt()
    const c1 = await computeKeyCommitment(key, 'file-a.txt', 1024, 0, salt)
    const c2 = await computeKeyCommitment(key, 'file-b.txt', 1024, 0, salt)
    expect(c1).not.toBe(c2)
  })

  it('changes when fileSize differs', async () => {
    const key = await generateMasterKey()
    const salt = generateSalt()
    const c1 = await computeKeyCommitment(key, 'test.txt', 1024, 0, salt)
    const c2 = await computeKeyCommitment(key, 'test.txt', 2048, 0, salt)
    expect(c1).not.toBe(c2)
  })

  it('changes when fileIndex differs', async () => {
    const key = await generateMasterKey()
    const salt = generateSalt()
    const c1 = await computeKeyCommitment(key, 'test.txt', 1024, 0, salt)
    const c2 = await computeKeyCommitment(key, 'test.txt', 1024, 1, salt)
    expect(c1).not.toBe(c2)
  })

  it('changes when salt differs', async () => {
    const key = await generateMasterKey()
    const salt1 = generateSalt()
    const salt2 = generateSalt()
    const c1 = await computeKeyCommitment(key, 'test.txt', 1024, 0, salt1)
    const c2 = await computeKeyCommitment(key, 'test.txt', 1024, 0, salt2)
    expect(c1).not.toBe(c2)
  })

  it('changes when key differs', async () => {
    const key1 = await generateMasterKey()
    const key2 = await generateMasterKey()
    const salt = generateSalt()
    const c1 = await computeKeyCommitment(key1, 'test.txt', 1024, 0, salt)
    const c2 = await computeKeyCommitment(key2, 'test.txt', 1024, 0, salt)
    expect(c1).not.toBe(c2)
  })

  it('works with imported (HKDF) keys', async () => {
    const masterKey = await generateMasterKey()
    const exported = await exportKey(masterKey)
    const imported = await importKey(exported)
    const salt = generateSalt()

    const c1 = await computeKeyCommitment(masterKey, 'test.txt', 1024, 0, salt)
    const c2 = await computeKeyCommitment(imported, 'test.txt', 1024, 0, salt)
    expect(c1).toBe(c2)
  })
})

describe('verifyKeyCommitment', () => {
  it('returns true for valid commitment', async () => {
    const key = await generateMasterKey()
    const salt = generateSalt()
    const commitment = await computeKeyCommitment(
      key,
      'test.txt',
      1024,
      0,
      salt,
    )
    const valid = await verifyKeyCommitment(
      key,
      'test.txt',
      1024,
      0,
      salt,
      commitment,
    )
    expect(valid).toBe(true)
  })

  it('returns false for tampered commitment', async () => {
    const key = await generateMasterKey()
    const salt = generateSalt()
    const commitment = await computeKeyCommitment(
      key,
      'test.txt',
      1024,
      0,
      salt,
    )
    // Tamper: flip a character
    const tampered = commitment.replace(
      commitment[0],
      commitment[0] === 'a' ? 'b' : 'a',
    )
    const valid = await verifyKeyCommitment(
      key,
      'test.txt',
      1024,
      0,
      salt,
      tampered,
    )
    expect(valid).toBe(false)
  })

  it('rejects undefined commitment', async () => {
    const key = await generateMasterKey()
    const salt = generateSalt()
    await expect(
      verifyKeyCommitment(key, 'test.txt', 1024, 0, salt, undefined),
    ).rejects.toThrow('Key commitment is required')
  })

  it('returns false when file metadata changed', async () => {
    const key = await generateMasterKey()
    const salt = generateSalt()
    const commitment = await computeKeyCommitment(
      key,
      'test.txt',
      1024,
      0,
      salt,
    )
    // Verify with different file size
    const valid = await verifyKeyCommitment(
      key,
      'test.txt',
      9999,
      0,
      salt,
      commitment,
    )
    expect(valid).toBe(false)
  })
})
