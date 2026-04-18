import { describe, expect, it } from 'vitest'

import { decryptGcm, encryptGcm, GCM_TAG_LENGTH, IV_LENGTH } from './aes-gcm'
import { generateMasterKey } from './master-key'

describe('encryptGcm / decryptGcm', () => {
  it('round-trips a byte buffer', async () => {
    const key = await generateMasterKey()
    const plaintext = new TextEncoder().encode('hello world')
    const ct = await encryptGcm(key, plaintext)
    expect(ct.iv.byteLength).toBe(IV_LENGTH)
    expect(ct.bytes.byteLength).toBeGreaterThanOrEqual(
      plaintext.byteLength + GCM_TAG_LENGTH,
    )
    const pt = await decryptGcm(key, ct)
    expect(new TextDecoder().decode(pt)).toBe('hello world')
  })

  it('produces a fresh IV per call (nonce-reuse safety)', async () => {
    const key = await generateMasterKey()
    const plaintext = new Uint8Array([1, 2, 3])
    const a = await encryptGcm(key, plaintext)
    const b = await encryptGcm(key, plaintext)
    // Overwhelmingly likely (12 random bytes): IVs differ.
    expect(a.iv).not.toEqual(b.iv)
    // And so do the ciphertexts — AES-GCM is nonce-dependent.
    expect(a.bytes).not.toEqual(b.bytes)
  })

  it('decrypt throws on a tampered auth tag', async () => {
    const key = await generateMasterKey()
    const ct = await encryptGcm(key, new Uint8Array([1, 2, 3]))
    // Flip the final byte — GCM's tag sits at the end of ``bytes``.
    const tampered = new Uint8Array(ct.bytes)
    tampered[tampered.byteLength - 1] ^= 0x01
    await expect(
      decryptGcm(key, { iv: ct.iv, bytes: tampered }),
    ).rejects.toThrow()
  })

  it('decrypt throws when IV length is wrong', async () => {
    const key = await generateMasterKey()
    const ct = await encryptGcm(key, new Uint8Array([1]))
    await expect(
      decryptGcm(key, { iv: new Uint8Array(8), bytes: ct.bytes }),
    ).rejects.toThrow(/Invalid IV length/)
  })

  it('decrypt throws when ciphertext is too short to hold the tag', async () => {
    const key = await generateMasterKey()
    await expect(
      decryptGcm(key, {
        iv: new Uint8Array(IV_LENGTH),
        bytes: new Uint8Array(5), // < 16 bytes
      }),
    ).rejects.toThrow(/too short/)
  })

  it('decrypt throws when key does not match', async () => {
    const k1 = await generateMasterKey()
    const k2 = await generateMasterKey()
    const ct = await encryptGcm(k1, new Uint8Array([9, 9, 9]))
    await expect(decryptGcm(k2, ct)).rejects.toThrow()
  })
})
