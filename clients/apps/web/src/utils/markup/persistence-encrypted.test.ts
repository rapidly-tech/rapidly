import { describe, expect, it } from 'vitest'

import { generateMasterKey } from '../crypto/master-key'
import { inMemoryStorage } from './persistence'
import { encryptedStorage } from './persistence-encrypted'

describe('encryptedStorage', () => {
  it('round-trips a byte buffer through encrypt + decrypt', async () => {
    const key = await generateMasterKey()
    const inner = inMemoryStorage()
    const store = encryptedStorage(inner, key)
    const bytes = new TextEncoder().encode('hello persistence')
    await store.put('room', bytes)
    const back = await store.get('room')
    expect(back).not.toBeNull()
    expect(new TextDecoder().decode(back!)).toBe('hello persistence')
  })

  it('actually encrypts — raw backing bytes do not contain the plaintext', async () => {
    const key = await generateMasterKey()
    const inner = inMemoryStorage()
    const store = encryptedStorage(inner, key)
    const bytes = new TextEncoder().encode('SUPER-SECRET-PAYLOAD-TOKEN')
    await store.put('room', bytes)
    const raw = await inner.get('room')
    expect(raw).not.toBeNull()
    const rawAsString = new TextDecoder('utf-8', { fatal: false }).decode(raw!)
    expect(rawAsString).not.toContain('SUPER-SECRET-PAYLOAD-TOKEN')
  })

  it('returns null when the key does not match', async () => {
    const keyA = await generateMasterKey()
    const keyB = await generateMasterKey()
    const inner = inMemoryStorage()
    await encryptedStorage(inner, keyA).put('room', new Uint8Array([1, 2, 3]))
    const back = await encryptedStorage(inner, keyB).get('room')
    expect(back).toBeNull()
  })

  it('returns null when the backing bytes were tampered with', async () => {
    const key = await generateMasterKey()
    const inner = inMemoryStorage()
    const store = encryptedStorage(inner, key)
    await store.put('room', new Uint8Array([1, 2, 3]))
    // Flip a byte in the ciphertext portion (past the IV) to break
    // the GCM auth tag.
    const raw = (await inner.get('room'))!
    raw[raw.length - 1] ^= 0xff
    await inner.put('room', raw)
    const back = await store.get('room')
    expect(back).toBeNull()
  })

  it('returns null when the backing entry is shorter than the IV', async () => {
    const key = await generateMasterKey()
    const inner = inMemoryStorage()
    await inner.put('room', new Uint8Array([1, 2, 3])) // 3 bytes — too short
    const back = await encryptedStorage(inner, key).get('room')
    expect(back).toBeNull()
  })

  it('returns null when the inner storage has no entry', async () => {
    const key = await generateMasterKey()
    const store = encryptedStorage(inMemoryStorage(), key)
    expect(await store.get('nothing')).toBeNull()
  })

  it('uses a fresh IV per put — same plaintext encrypts differently', async () => {
    const key = await generateMasterKey()
    const innerA = inMemoryStorage()
    const innerB = inMemoryStorage()
    const storeA = encryptedStorage(innerA, key)
    const storeB = encryptedStorage(innerB, key)
    const plaintext = new Uint8Array([1, 2, 3, 4, 5])
    await storeA.put('room', plaintext)
    await storeB.put('room', plaintext)
    const rawA = (await innerA.get('room'))!
    const rawB = (await innerB.get('room'))!
    expect(rawA).not.toEqual(rawB)
  })

  it('delete flows through to the inner storage', async () => {
    const key = await generateMasterKey()
    const inner = inMemoryStorage()
    const store = encryptedStorage(inner, key)
    await store.put('room', new Uint8Array([1, 2, 3]))
    expect(await inner.get('room')).not.toBeNull()
    await store.delete('room')
    expect(await inner.get('room')).toBeNull()
  })
})
