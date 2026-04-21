/**
 * Encrypted wrapper over any ``PersistenceStorage``.
 *
 * Rapidly's policy is E2EE-at-app-layer (see ``CLAUDE.md`` memory).
 * The local IndexedDB snapshot is already inside the user's device
 * boundary, but a small, shared device (office machine, family iPad)
 * makes local at-rest encryption cheap and obvious insurance:
 * shoulder-surfer with DevTools open can't lift the raw doc state
 * without the key.
 *
 * Wire format
 * -----------
 * Each stored value is ``[iv:12][ciphertext-with-gcm-tag]`` packed
 * into a single ``Uint8Array``. The wrapper is the only party that
 * parses this format — consumers of ``PersistenceStorage`` stay
 * symmetric.
 *
 * Failure modes
 * -------------
 * Decrypt failures (wrong key, tampered bytes, pre-encryption
 * upgrade) return ``null`` from ``get`` rather than throwing. A user
 * who rotated their device key and now can't read the old snapshot
 * should see an empty room, not a crash. Log the failure so
 * telemetry can see it if the inner storage still reports present
 * keys.
 */

import { decryptGcm, encryptGcm, IV_LENGTH } from '../crypto/aes-gcm'

import type { PersistenceStorage } from './persistence'

/** Wrap ``inner`` with AES-GCM encryption using the supplied
 *  ``CryptoKey``. The key should be AES-GCM-capable (256-bit in the
 *  Rapidly crypto stack; any length Web Crypto accepts will work).
 *  Returns a drop-in ``PersistenceStorage`` so callers swap it in
 *  with a single line:
 *
 *  ```ts
 *  const storage = encryptedStorage(indexedDbStorage(), roomKey)
 *  createPersistence({ doc, roomId, storage })
 *  ```
 */
export function encryptedStorage(
  inner: PersistenceStorage,
  key: CryptoKey,
): PersistenceStorage {
  return {
    async get(roomKey) {
      const raw = await inner.get(roomKey)
      if (!raw || raw.byteLength <= IV_LENGTH) return null
      const iv = raw.slice(0, IV_LENGTH)
      const bytes = raw.slice(IV_LENGTH)
      try {
        return await decryptGcm(key, { iv, bytes })
      } catch {
        // Key mismatch or tampered data. Treat as ""entry not usable""
        // so the caller re-initialises rather than surfacing a stack
        // trace to the user.
        return null
      }
    },
    async put(roomKey, value) {
      const { iv, bytes } = await encryptGcm(key, value)
      const framed = new Uint8Array(iv.byteLength + bytes.byteLength)
      framed.set(iv, 0)
      framed.set(bytes, iv.byteLength)
      await inner.put(roomKey, framed)
    },
    async delete(roomKey) {
      await inner.delete(roomKey)
    },
  }
}
