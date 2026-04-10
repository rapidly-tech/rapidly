/**
 * Client-side encryption and comparison utilities.
 *
 * Contains two distinct sets of utilities:
 * - File sharing: secureCompare, randomString, hashPassword (Web Crypto)
 * - Secret sharing: encryptMessage, decryptMessage, decryptFile (OpenPGP)
 *
 * OpenPGP is loaded lazily to avoid adding ~200KB to pages that don't need it.
 */

import type { DecryptMessageResult } from 'openpgp'
import { toHex } from './hex'

// Re-export from shared leaf module (no openpgp dependency)
export { secureCompare } from './secure-compare'

// Lazy-load openpgp only when needed
async function loadOpenPGP() {
  return import('openpgp')
}

// ── Random Generation ──

/**
 * Generate a random password (22 characters, alphanumeric).
 */
export function randomString(): string {
  const possible =
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
  const maxUnbiased = 256 - (256 % possible.length) // 248 for 62 chars
  let text = ''
  while (text.length < 22) {
    const array = new Uint8Array(32)
    crypto.getRandomValues(array)
    for (let i = 0; i < array.length && text.length < 22; i++) {
      if (array[i] < maxUnbiased) {
        text += possible.charAt(array[i] % possible.length)
      }
    }
  }
  return text
}

// ── Password Hashing ──

/**
 * Hash a password using SHA-256.
 * Returns a 64-character hex string that is URL-safe and opaque.
 * This prevents the actual password from appearing in browser history.
 *
 * Note: SHA-256 is used rather than a slow KDF (bcrypt/Argon2) because
 * the comparison happens over P2P (not against stored hashes), and the
 * auto-generated passwords from {@link randomString} have ~131 bits of
 * entropy.  If user-chosen passwords are ever supported, consider adding
 * a slow KDF layer.
 */
export async function hashPassword(password: string): Promise<string> {
  const encoder = new TextEncoder()
  const data = encoder.encode(password)
  const hashBuffer = await crypto.subtle.digest('SHA-256', data)
  return toHex(new Uint8Array(hashBuffer))
}

// ── OpenPGP Message Encryption ──

/**
 * Encrypt a text message using OpenPGP.
 */
export async function encryptMessage(
  data: string,
  password: string,
): Promise<string> {
  const { createMessage, encrypt } = await loadOpenPGP()
  return encrypt({
    message: await createMessage({ text: data }),
    passwords: [password],
  }) as Promise<string>
}

/**
 * Decrypt a text message using OpenPGP.
 */
export async function decryptMessage(
  data: string,
  password: string,
): Promise<DecryptMessageResult> {
  const { readMessage, decrypt } = await loadOpenPGP()
  return decrypt({
    message: await readMessage({ armoredMessage: data }),
    passwords: [password],
    format: 'utf8',
  })
}

// ── OpenPGP File Decryption ──

/**
 * Decrypt a file using OpenPGP.
 */
export async function decryptFile(
  data: string,
  password: string,
): Promise<DecryptMessageResult> {
  const { readMessage, decrypt } = await loadOpenPGP()
  return decrypt({
    message: await readMessage({ armoredMessage: data }),
    passwords: [password],
    format: 'binary',
  })
}
