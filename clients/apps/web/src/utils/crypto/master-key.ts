/**
 * Master-key generation + URL-fragment export/import.
 *
 * The chamber's E2EE rollout uses the same pattern the file-sharing
 * chamber already ships: a 256-bit AES-GCM master key generated on
 * the host, embedded in the invite URL's fragment (``#k=...``), and
 * imported on the guest side. The fragment is not transmitted in the
 * HTTP request, so the Rapidly server never sees it.
 */

const KEY_LENGTH = 256

/** Generate a fresh 256-bit AES-GCM master key. Extractable so the
 *  host can base64url-encode it into the invite fragment. */
export async function generateMasterKey(): Promise<CryptoKey> {
  return crypto.subtle.generateKey(
    { name: 'AES-GCM', length: KEY_LENGTH },
    true,
    ['encrypt', 'decrypt'],
  )
}

/** Generate a fresh 16-byte random salt for HKDF derivation.
 *  Per NIST SP 800-56C, a non-empty salt strengthens derived keys. */
export function generateSalt(): Uint8Array {
  return crypto.getRandomValues(new Uint8Array(16))
}

// ── base64url codec ──
//
// Duplicated from ``utils/file-sharing/encryption-core.ts`` deliberately
// to keep this module dependency-free — Collab's E2EE code path should
// not pull in the file-sharing module's ~1000-line surface.

function toBase64url(bytes: Uint8Array): string {
  let s = ''
  for (let i = 0; i < bytes.byteLength; i += 0x8000) {
    s += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  }
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function fromBase64url(s: string): Uint8Array {
  const padded = s.replace(/-/g, '+').replace(/_/g, '/')
  const pad = padded.length % 4 === 0 ? '' : '='.repeat(4 - (padded.length % 4))
  const bin = atob(padded + pad)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i)
  return bytes
}

/** Export a master key as a base64url string safe for URL fragments. */
export async function exportMasterKey(key: CryptoKey): Promise<string> {
  const raw = await crypto.subtle.exportKey('raw', key)
  return toBase64url(new Uint8Array(raw))
}

/** Import a master key from a base64url URL-fragment value. */
export async function importMasterKey(base64url: string): Promise<CryptoKey> {
  const raw = fromBase64url(base64url)
  if (raw.byteLength !== 32) {
    throw new Error(
      `Invalid master key length: expected 32 bytes, got ${raw.byteLength}`,
    )
  }
  return crypto.subtle.importKey(
    'raw',
    raw as BufferSource,
    { name: 'AES-GCM', length: KEY_LENGTH },
    true,
    ['encrypt', 'decrypt'],
  )
}

export function exportSalt(salt: Uint8Array): string {
  return toBase64url(salt)
}

export function importSalt(base64url: string): Uint8Array {
  const salt = fromBase64url(base64url)
  if (salt.byteLength !== 16) {
    throw new Error(
      `Invalid salt length: expected 16 bytes, got ${salt.byteLength}`,
    )
  }
  return salt
}
