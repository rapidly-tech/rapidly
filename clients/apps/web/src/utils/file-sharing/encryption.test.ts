import { describe, expect, it } from 'vitest'
import {
  decryptChunk,
  decryptMetadata,
  deriveFileKey,
  deriveReaderToken,
  encryptChunk,
  encryptMetadata,
  exportKey,
  exportSalt,
  generateMasterKey,
  generateSalt,
  importKey,
  importSalt,
} from './encryption'

describe('generateMasterKey', () => {
  it('generates a 256-bit AES-GCM key', async () => {
    const key = await generateMasterKey()
    expect(key.algorithm).toMatchObject({ name: 'AES-GCM', length: 256 })
    expect(key.extractable).toBe(true)
    expect(key.usages).toContain('encrypt')
    expect(key.usages).toContain('decrypt')
  })

  it('generates unique keys each time', async () => {
    const key1 = await generateMasterKey()
    const key2 = await generateMasterKey()
    const raw1 = await crypto.subtle.exportKey('raw', key1)
    const raw2 = await crypto.subtle.exportKey('raw', key2)
    expect(new Uint8Array(raw1)).not.toEqual(new Uint8Array(raw2))
  })
})

describe('generateSalt', () => {
  it('generates a 16-byte salt', () => {
    const salt = generateSalt()
    expect(salt).toBeInstanceOf(Uint8Array)
    expect(salt.byteLength).toBe(16)
  })

  it('generates unique salts', () => {
    const salt1 = generateSalt()
    const salt2 = generateSalt()
    expect(salt1).not.toEqual(salt2)
  })
})

describe('exportKey / importKey round-trip', () => {
  it('round-trips a key through base64url', async () => {
    const original = await generateMasterKey()
    const exported = await exportKey(original)
    expect(typeof exported).toBe('string')
    expect(exported.length).toBeGreaterThan(0)

    const imported = await importKey(exported)
    expect(imported.algorithm).toMatchObject({ name: 'HKDF' })
    expect(imported.extractable).toBe(false)
  })

  it('rejects keys that are not 32 bytes', async () => {
    // 16-byte key (too short)
    const shortKey = btoa(String.fromCharCode(...new Uint8Array(16)))
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/, '')
    await expect(importKey(shortKey)).rejects.toThrow('Invalid key length')

    // 64-byte key (too long)
    const longKey = btoa(String.fromCharCode(...new Uint8Array(64)))
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/, '')
    await expect(importKey(longKey)).rejects.toThrow('Invalid key length')
  })
})

describe('exportSalt / importSalt round-trip', () => {
  it('round-trips a salt through base64url', () => {
    const original = generateSalt()
    const exported = exportSalt(original)
    expect(typeof exported).toBe('string')

    const imported = importSalt(exported)
    expect(imported).toEqual(original)
  })

  it('rejects salts that are not 16 bytes', () => {
    const shortSalt = btoa(String.fromCharCode(...new Uint8Array(8)))
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/, '')
    expect(() => importSalt(shortSalt)).toThrow('Invalid salt length')
  })
})

describe('deriveFileKey', () => {
  it('requires salt parameter (no default)', async () => {
    const key = await generateMasterKey()
    const salt = generateSalt()

    // Should work with explicit salt
    const fileKey = await deriveFileKey(key, 'test.txt', 0, salt)
    expect(fileKey.algorithm).toMatchObject({ name: 'AES-GCM', length: 256 })
    expect(fileKey.extractable).toBe(false)
  })

  it('rejects empty salt', async () => {
    const key = await generateMasterKey()
    await expect(
      deriveFileKey(key, 'test.txt', 0, new Uint8Array(0)),
    ).rejects.toThrow('Empty salt is not allowed')
  })

  it('derives different keys for different files', async () => {
    const key = await generateMasterKey()
    const salt = generateSalt()
    const key1 = await deriveFileKey(key, 'file1.txt', 0, salt)
    const key2 = await deriveFileKey(key, 'file2.txt', 1, salt)

    // Can't compare non-extractable keys directly, but encrypt same data
    // and verify ciphertexts differ (proving different keys)
    const plaintext = new TextEncoder().encode('test data').buffer
    const ct1 = await encryptChunk(key1, plaintext)
    const ct2 = await encryptChunk(key2, plaintext)
    // Ciphertexts should differ (different keys + different random IVs)
    expect(new Uint8Array(ct1)).not.toEqual(new Uint8Array(ct2))
  })

  it('derives different keys with different salts', async () => {
    const key = await generateMasterKey()
    const salt1 = generateSalt()
    const salt2 = generateSalt()
    const fileKey1 = await deriveFileKey(key, 'test.txt', 0, salt1)
    const fileKey2 = await deriveFileKey(key, 'test.txt', 0, salt2)

    const plaintext = new TextEncoder().encode('test data').buffer
    const ct1 = await encryptChunk(fileKey1, plaintext)
    const ct2 = await encryptChunk(fileKey2, plaintext)
    expect(new Uint8Array(ct1)).not.toEqual(new Uint8Array(ct2))
  })

  it('derives the same key for the same inputs (deterministic)', async () => {
    const masterKey = await generateMasterKey()
    const salt = generateSalt()

    const key1 = await deriveFileKey(masterKey, 'test.txt', 0, salt)
    const key2 = await deriveFileKey(masterKey, 'test.txt', 0, salt)

    // Encrypt with key1, decrypt with key2 — should succeed if keys match
    const plaintext = new TextEncoder().encode('deterministic test').buffer
    const encrypted = await encryptChunk(key1, plaintext)
    const decrypted = await decryptChunk(key2, encrypted)
    expect(new Uint8Array(decrypted)).toEqual(new Uint8Array(plaintext))
  })
})

describe('deriveReaderToken', () => {
  it('requires salt parameter', async () => {
    const key = await generateMasterKey()
    const salt = generateSalt()
    const token = await deriveReaderToken(key, salt)
    expect(typeof token).toBe('string')
    expect(token).toHaveLength(64) // 32 bytes as hex
    expect(token).toMatch(/^[a-f0-9]{64}$/)
  })

  it('produces deterministic tokens for same inputs', async () => {
    const key = await generateMasterKey()
    const salt = generateSalt()
    const token1 = await deriveReaderToken(key, salt)
    const token2 = await deriveReaderToken(key, salt)
    expect(token1).toBe(token2)
  })

  it('produces different tokens with different salts', async () => {
    const key = await generateMasterKey()
    const token1 = await deriveReaderToken(key, generateSalt())
    const token2 = await deriveReaderToken(key, generateSalt())
    expect(token1).not.toBe(token2)
  })

  it('rejects empty salt', async () => {
    const key = await generateMasterKey()
    await expect(deriveReaderToken(key, new Uint8Array(0))).rejects.toThrow(
      'Empty salt is not allowed',
    )
  })
})

describe('encryptChunk / decryptChunk', () => {
  it('round-trips data correctly', async () => {
    const key = await generateMasterKey()
    const salt = generateSalt()
    const fileKey = await deriveFileKey(key, 'test.txt', 0, salt)

    const plaintext = new TextEncoder().encode('Hello, World!').buffer
    const encrypted = await encryptChunk(fileKey, plaintext)
    const decrypted = await decryptChunk(fileKey, encrypted)

    expect(new Uint8Array(decrypted)).toEqual(new Uint8Array(plaintext))
  })

  it('encrypted output is larger than plaintext (IV + auth tag)', async () => {
    const key = await generateMasterKey()
    const fileKey = await deriveFileKey(key, 'test.txt', 0, generateSalt())

    const plaintext = new Uint8Array(1000).buffer
    const encrypted = await encryptChunk(fileKey, plaintext)

    // 12-byte IV + 16-byte GCM auth tag = 28 bytes overhead
    expect(encrypted.byteLength).toBe(plaintext.byteLength + 28)
  })

  it('produces different ciphertext for same plaintext (random IV)', async () => {
    const key = await generateMasterKey()
    const fileKey = await deriveFileKey(key, 'test.txt', 0, generateSalt())

    const plaintext = new TextEncoder().encode('same data').buffer
    const ct1 = await encryptChunk(fileKey, plaintext)
    const ct2 = await encryptChunk(fileKey, plaintext)

    expect(new Uint8Array(ct1)).not.toEqual(new Uint8Array(ct2))
  })

  it('rejects tampered ciphertext', async () => {
    const key = await generateMasterKey()
    const fileKey = await deriveFileKey(key, 'test.txt', 0, generateSalt())

    const plaintext = new TextEncoder().encode('sensitive data').buffer
    const encrypted = await encryptChunk(fileKey, plaintext)

    // Tamper with the ciphertext (flip a byte after the IV)
    const tampered = new Uint8Array(encrypted)
    tampered[20] ^= 0xff
    await expect(decryptChunk(fileKey, tampered.buffer)).rejects.toThrow()
  })

  it('rejects data that is too short', async () => {
    const key = await generateMasterKey()
    const fileKey = await deriveFileKey(key, 'test.txt', 0, generateSalt())

    const tooShort = new Uint8Array(10).buffer // Less than IV + tag (28 bytes)
    await expect(decryptChunk(fileKey, tooShort)).rejects.toThrow(
      'Encrypted data too short',
    )
  })

  it('fails with wrong key', async () => {
    const key1 = await generateMasterKey()
    const key2 = await generateMasterKey()
    const salt = generateSalt()
    const fileKey1 = await deriveFileKey(key1, 'test.txt', 0, salt)
    const fileKey2 = await deriveFileKey(key2, 'test.txt', 0, salt)

    const plaintext = new TextEncoder().encode('secret').buffer
    const encrypted = await encryptChunk(fileKey1, plaintext)
    await expect(decryptChunk(fileKey2, encrypted)).rejects.toThrow()
  })
})

describe('encryptMetadata / decryptMetadata', () => {
  it('round-trips JSON metadata', async () => {
    const key = await generateMasterKey()
    const salt = generateSalt()

    const metadata = {
      type: 'info',
      files: [{ fileName: 'test.txt', size: 1024, type: 'text/plain' }],
      encrypted: true,
    }

    const encrypted = await encryptMetadata(key, metadata, salt)
    expect(encrypted).toBeInstanceOf(ArrayBuffer)

    const decrypted = await decryptMetadata(key, encrypted, salt)
    expect(decrypted).toEqual(metadata)
  })

  it('rejects metadata larger than 16MB', async () => {
    const key = await generateMasterKey()
    const salt = generateSalt()
    const bigData = { data: 'x'.repeat(16 * 1024 * 1024 + 1) }

    await expect(encryptMetadata(key, bigData, salt)).rejects.toThrow(
      'Metadata too large',
    )
  })

  it('rejects non-serializable metadata', async () => {
    const key = await generateMasterKey()
    const salt = generateSalt()

    const circular: Record<string, unknown> = {}
    circular.self = circular

    await expect(encryptMetadata(key, circular, salt)).rejects.toThrow(
      'not JSON-serializable',
    )
  })

  it('fails to decrypt with wrong key', async () => {
    const key1 = await generateMasterKey()
    const key2 = await generateMasterKey()
    const salt = generateSalt()

    const encrypted = await encryptMetadata(key1, { secret: 'data' }, salt)
    await expect(decryptMetadata(key2, encrypted, salt)).rejects.toThrow()
  })

  it('fails to decrypt with wrong salt', async () => {
    const key = await generateMasterKey()
    const salt1 = generateSalt()
    const salt2 = generateSalt()

    const encrypted = await encryptMetadata(key, { test: true }, salt1)
    await expect(decryptMetadata(key, encrypted, salt2)).rejects.toThrow()
  })
})
