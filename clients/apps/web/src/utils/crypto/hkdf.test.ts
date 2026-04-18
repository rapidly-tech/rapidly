import { describe, expect, it } from 'vitest'

import { decryptGcm, encryptGcm } from './aes-gcm'
import { deriveSubKey, infoFor } from './hkdf'
import { generateMasterKey, generateSalt } from './master-key'

describe('deriveSubKey', () => {
  it('derives a usable AES-GCM sub-key from a master', async () => {
    const master = await generateMasterKey()
    const salt = generateSalt()
    const sub = await deriveSubKey(master, infoFor('collab', 'sync'), salt)
    const ct = await encryptGcm(sub, new Uint8Array([1, 2, 3]))
    const pt = await decryptGcm(sub, ct)
    expect(Array.from(pt)).toEqual([1, 2, 3])
  })

  it('is deterministic — same inputs produce a key that decrypts the same ciphertext', async () => {
    const master = await generateMasterKey()
    const salt = generateSalt()
    const info = infoFor('collab', 'sync')
    const sub1 = await deriveSubKey(master, info, salt)
    const sub2 = await deriveSubKey(master, info, salt)
    const ct = await encryptGcm(sub1, new Uint8Array([4, 5]))
    const pt = await decryptGcm(sub2, ct)
    expect(Array.from(pt)).toEqual([4, 5])
  })

  it('different info strings produce key-separated sub-keys', async () => {
    // The whole point of HKDF info binding: a sync-purpose key must
    // NOT decrypt awareness-purpose ciphertext and vice versa.
    const master = await generateMasterKey()
    const salt = generateSalt()
    const sync = await deriveSubKey(master, infoFor('collab', 'sync'), salt)
    const awareness = await deriveSubKey(
      master,
      infoFor('collab', 'awareness'),
      salt,
    )
    const ct = await encryptGcm(sync, new Uint8Array([7]))
    await expect(decryptGcm(awareness, ct)).rejects.toThrow()
  })

  it('different chambers with the same purpose produce key-separated sub-keys', async () => {
    // Belt-and-braces: if a master key is ever (wrongly) reused across
    // chambers, the chamber-name prefix in ``info`` keeps derived
    // keys distinct.
    const master = await generateMasterKey()
    const salt = generateSalt()
    const collabSync = await deriveSubKey(
      master,
      infoFor('collab', 'sync'),
      salt,
    )
    const screenSync = await deriveSubKey(
      master,
      infoFor('screen', 'sync'),
      salt,
    )
    const ct = await encryptGcm(collabSync, new Uint8Array([1]))
    await expect(decryptGcm(screenSync, ct)).rejects.toThrow()
  })

  it('rejects empty salt', async () => {
    const master = await generateMasterKey()
    await expect(
      deriveSubKey(master, infoFor('collab', 'sync'), new Uint8Array(0)),
    ).rejects.toThrow(/Empty salt/)
  })
})

describe('infoFor', () => {
  it('encodes as chamber:purpose:version', () => {
    expect(new TextDecoder().decode(infoFor('collab', 'sync'))).toBe(
      'collab:sync:v1',
    )
    expect(new TextDecoder().decode(infoFor('collab', 'sync', 'v2'))).toBe(
      'collab:sync:v2',
    )
  })
})
