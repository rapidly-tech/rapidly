import { describe, expect, it } from 'vitest'

import { decryptGcm, encryptGcm } from './aes-gcm'
import {
  exportMasterKey,
  exportSalt,
  generateMasterKey,
  generateSalt,
  importMasterKey,
  importSalt,
} from './master-key'

describe('generateMasterKey / export / import', () => {
  it('round-trips through base64url', async () => {
    const key1 = await generateMasterKey()
    const encoded = await exportMasterKey(key1)
    expect(encoded).toMatch(/^[A-Za-z0-9_-]+$/)
    const key2 = await importMasterKey(encoded)
    // Different CryptoKey handles, but decrypt on side B should
    // succeed on ciphertext encrypted on side A.
    const ct = await encryptGcm(key1, new Uint8Array([1, 2, 3]))
    const pt = await decryptGcm(key2, ct)
    expect(Array.from(pt)).toEqual([1, 2, 3])
  })

  it('rejects a mis-sized master key', async () => {
    await expect(importMasterKey('AAAA')).rejects.toThrow(
      /Invalid master key length/,
    )
  })
})

describe('generateSalt / export / import', () => {
  it('generates 16-byte salts', () => {
    const salt = generateSalt()
    expect(salt.byteLength).toBe(16)
  })

  it('produces fresh randomness per call', () => {
    const a = generateSalt()
    const b = generateSalt()
    expect(a).not.toEqual(b)
  })

  it('round-trips through base64url', () => {
    const salt = generateSalt()
    const roundtripped = importSalt(exportSalt(salt))
    expect(roundtripped).toEqual(salt)
  })

  it('rejects a mis-sized salt on import', () => {
    // Export 8 bytes, decode should throw.
    const tooShort = exportSalt(new Uint8Array(8))
    expect(() => importSalt(tooShort)).toThrow(/Invalid salt length/)
  })
})
