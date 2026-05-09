/**
 * Generic AES-256-GCM primitives for P2P chambers.
 *
 * The file-sharing chamber has its own ``utils/file-sharing/encryption.ts``
 * with domain-specific framing (per-chunk headers, reader tokens,
 * metadata commitment). This module is the **portable subset** the
 * Collab chamber needs for its E2EE v1.1 rollout — no chunk framing,
 * no file names, no reader tokens. Just encrypt-bytes / decrypt-bytes
 * with explicit IV handling so callers can choose their own envelope
 * (Collab uses a ``{t, iv, bytes}`` JSON envelope on the DC; future
 * chambers can reuse this without touching the file-sharing module).
 *
 * See ``specs/collab-e2ee.md`` for why these primitives live here
 * instead of being pulled out of ``encryption.ts``: extracting without
 * disturbing the shipping file-sharing path would require careful
 * audit of ~20 call sites. A clean new module is safer and almost
 * free — Web Crypto itself is ~3 lines per operation.
 */

/** AES-GCM recommended IV length in bytes (NIST SP 800-38D §8.2.1). */
export const IV_LENGTH = 12

/** AES-GCM authentication tag length in bytes (always 16 for browser
 *  Web Crypto — the spec allows 12 / 13 / 14 / 15 / 16 but browsers
 *  default to 16, so we hardcode it for the size check in decrypt). */
export const GCM_TAG_LENGTH = 16

export interface GcmCiphertext {
  /** 12 random bytes, fresh per call. Must NOT be reused across calls
   *  with the same key — GCM nonce-reuse is catastrophic. */
  iv: Uint8Array
  /** Ciphertext with the 16-byte auth tag appended. */
  bytes: Uint8Array
}

/** Encrypt a plaintext buffer with a fresh IV. */
export async function encryptGcm(
  key: CryptoKey,
  plaintext: Uint8Array,
): Promise<GcmCiphertext> {
  const iv = crypto.getRandomValues(new Uint8Array(IV_LENGTH))
  const ciphertext = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    key,
    plaintext as BufferSource,
  )
  return { iv, bytes: new Uint8Array(ciphertext) }
}

/** Decrypt a GCM envelope. Throws on auth-tag failure (Web Crypto
 *  surfaces this as a plain ``OperationError``). Callers should
 *  treat any throw here as "frame tampered or key mismatch, drop". */
export async function decryptGcm(
  key: CryptoKey,
  envelope: GcmCiphertext,
): Promise<Uint8Array> {
  if (envelope.iv.byteLength !== IV_LENGTH) {
    throw new Error(
      `Invalid IV length: expected ${IV_LENGTH}, got ${envelope.iv.byteLength}`,
    )
  }
  if (envelope.bytes.byteLength < GCM_TAG_LENGTH) {
    throw new Error(
      `Ciphertext too short: expected ≥ ${GCM_TAG_LENGTH} bytes (auth tag), got ${envelope.bytes.byteLength}`,
    )
  }
  const plaintext = await crypto.subtle.decrypt(
    { name: 'AES-GCM', iv: envelope.iv as BufferSource },
    key,
    envelope.bytes as BufferSource,
  )
  return new Uint8Array(plaintext)
}
