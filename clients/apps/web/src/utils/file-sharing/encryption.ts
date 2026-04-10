/**
 * AES-256-GCM end-to-end encryption for P2P file transfers.
 *
 * Uses Web Crypto API for streaming encryption. The master key is generated
 * on the uploader side and embedded in the URL fragment (never sent to server).
 * Per-file keys are derived via HKDF to provide key separation.
 *
 * Each encrypted chunk is: IV (12 bytes) || AES-GCM ciphertext (includes 16-byte auth tag)
 * AES-GCM provides authenticated encryption, so integrity is verified on decryption.
 */

import { toHex } from './hex'
import { secureCompare } from './secure-compare'

// ── Constants ──

export const IV_LENGTH = 12
const KEY_LENGTH = 256

// ── HKDF Key Cache ──

/**
 * Cache for HKDF key handles derived from AES-GCM master keys.
 * Avoids repeatedly exporting raw key material to the JS heap.
 */
const hkdfKeyCache = new WeakMap<CryptoKey, CryptoKey>()

/**
 * Get an HKDF key from a master key.
 * If already HKDF (downloader), use directly; if AES-GCM (uploader), re-import
 * and cache to avoid repeated raw key exposure in the JS heap.
 */
async function getHkdfKey(masterKey: CryptoKey): Promise<CryptoKey> {
  if (masterKey.algorithm.name === 'HKDF') {
    return masterKey
  }
  const cached = hkdfKeyCache.get(masterKey)
  if (cached) return cached

  const rawMaster = await crypto.subtle.exportKey('raw', masterKey)
  const hkdfKey = await crypto.subtle.importKey(
    'raw',
    rawMaster,
    'HKDF',
    false,
    ['deriveKey'],
  )
  hkdfKeyCache.set(masterKey, hkdfKey)
  return hkdfKey
}

// ── Key Generation and Import/Export ──

/**
 * Generate a new AES-256 master encryption key.
 */
export async function generateMasterKey(): Promise<CryptoKey> {
  return crypto.subtle.generateKey(
    { name: 'AES-GCM', length: KEY_LENGTH },
    true, // extractable - needed for export to URL
    ['encrypt', 'decrypt'],
  )
}

/**
 * Generate a random 16-byte salt for HKDF key derivation.
 * Per NIST SP 800-56C, using a random salt strengthens derived keys.
 */
export function generateSalt(): Uint8Array {
  return crypto.getRandomValues(new Uint8Array(16))
}

/**
 * Export a salt to a base64url string for embedding in URL fragments.
 */
export function exportSalt(salt: Uint8Array): string {
  // Use .slice() to get an exact-length copy — avoids including excess bytes
  // if salt is a subarray of a larger backing ArrayBuffer
  return arrayBufferToBase64url(
    (salt.buffer as ArrayBuffer).slice(
      salt.byteOffset,
      salt.byteOffset + salt.byteLength,
    ),
  )
}

/**
 * Import a salt from a base64url string (from URL fragment).
 */
export function importSalt(base64url: string): Uint8Array {
  const salt = new Uint8Array(base64urlToArrayBuffer(base64url))
  // Validate salt is exactly 16 bytes
  if (salt.byteLength !== 16) {
    throw new Error(
      `Invalid salt length: expected 16 bytes, got ${salt.byteLength}`,
    )
  }
  return salt
}

/**
 * Export a CryptoKey to a base64url string for embedding in URL fragments.
 */
export async function exportKey(key: CryptoKey): Promise<string> {
  const raw = await crypto.subtle.exportKey('raw', key)
  return arrayBufferToBase64url(raw)
}

/**
 * Import a CryptoKey from a base64url string (from URL fragment).
 */
export async function importKey(base64url: string): Promise<CryptoKey> {
  const raw = base64urlToArrayBuffer(base64url)
  // Validate key is exactly 256 bits (32 bytes)
  if (raw.byteLength !== 32) {
    throw new Error(
      `Invalid key length: expected 32 bytes, got ${raw.byteLength}`,
    )
  }
  // Import directly as HKDF key material — least privilege, non-extractable
  // The master key is only used to derive per-file keys, never for direct encryption
  return crypto.subtle.importKey('raw', raw, 'HKDF', false, ['deriveKey'])
}

// ── Key Derivation ──

/**
 * Derive a per-file encryption key from the master key using HKDF.
 *
 * Each file gets its own derived key to provide key separation.
 * This ensures that compromising one file's key material doesn't
 * compromise other files in the same transfer.
 */
export async function deriveFileKey(
  masterKey: CryptoKey,
  fileName: string,
  fileIndex: number,
  salt: Uint8Array,
): Promise<CryptoKey> {
  if (salt.byteLength === 0) {
    throw new Error(
      'Empty salt is not allowed — cannot derive a secure file key.',
    )
  }

  const hkdfKey = await getHkdfKey(masterKey)

  // Domain separation via info field per NIST SP 800-56C
  // Both fileIndex and fileName in info ensure unique keys per file
  const encoder = new TextEncoder()
  const info = encoder.encode(`file-sharing:${fileIndex}:${fileName}`)

  return crypto.subtle.deriveKey(
    {
      name: 'HKDF',
      hash: 'SHA-256',
      salt: salt as BufferSource,
      info,
    },
    hkdfKey,
    { name: 'AES-GCM', length: KEY_LENGTH },
    false,
    ['encrypt', 'decrypt'],
  )
}

// ── Chunk Encryption/Decryption ──

/**
 * Encrypt a chunk using AES-256-GCM.
 *
 * Returns: IV (12 bytes) || ciphertext (includes 16-byte GCM auth tag)
 * The random IV ensures each chunk produces unique ciphertext even with identical plaintext.
 */
export async function encryptChunk(
  key: CryptoKey,
  plaintext: ArrayBuffer,
): Promise<ArrayBuffer> {
  const iv = crypto.getRandomValues(new Uint8Array(IV_LENGTH))

  const ciphertext = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    key,
    plaintext,
  )

  // Prepend IV to ciphertext
  const result = new Uint8Array(IV_LENGTH + ciphertext.byteLength)
  result.set(iv, 0)
  result.set(new Uint8Array(ciphertext), IV_LENGTH)

  // Use .slice() to ensure an exact-sized ArrayBuffer — result.buffer may
  // reference a larger backing store on some engines (shared ArrayBuffer).
  return result.buffer.slice(
    result.byteOffset,
    result.byteOffset + result.byteLength,
  ) as ArrayBuffer
}

/**
 * Decrypt a chunk using AES-256-GCM.
 *
 * Input format: IV (12 bytes) || ciphertext (with 16-byte GCM auth tag)
 * Throws if the authentication tag verification fails (tampered data).
 */
export const GCM_TAG_LENGTH = 16

export async function decryptChunk(
  key: CryptoKey,
  encrypted: ArrayBuffer,
): Promise<ArrayBuffer> {
  if (encrypted.byteLength < IV_LENGTH + GCM_TAG_LENGTH) {
    throw new Error(
      `Encrypted data too short: expected at least ${IV_LENGTH + GCM_TAG_LENGTH} bytes, got ${encrypted.byteLength}`,
    )
  }
  const data = new Uint8Array(encrypted)
  const iv = data.slice(0, IV_LENGTH)
  const ciphertext = data.slice(IV_LENGTH)

  return crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, ciphertext)
}

// ── Reader Authorization ──

/**
 * Derive a reader authorization token from the master key.
 *
 * This token proves the downloader has the full URL (with encryption key).
 * The server validates this token before revealing channel info, preventing
 * slug enumeration attacks.
 *
 * Returns a 64-character hex string.
 */
export async function deriveReaderToken(
  masterKey: CryptoKey,
  salt: Uint8Array,
): Promise<string> {
  if (salt.byteLength === 0) {
    throw new Error(
      'Empty salt is not allowed — cannot derive a secure reader token.',
    )
  }

  const hkdfKey = await getHkdfKey(masterKey)

  const encoder = new TextEncoder()
  const info = encoder.encode('file-sharing-reader-auth')

  // Derive a key, then export its raw bytes as the token
  const tokenKey = await crypto.subtle.deriveKey(
    {
      name: 'HKDF',
      hash: 'SHA-256',
      salt: salt as BufferSource,
      info,
    },
    hkdfKey,
    { name: 'AES-GCM', length: KEY_LENGTH },
    true, // extractable so we can export
    ['encrypt'],
  )

  const rawBytes = await crypto.subtle.exportKey('raw', tokenKey)
  return toHex(new Uint8Array(rawBytes))
}

// ── File Hashing ──

/**
 * Compute the SHA-256 hash of a File/Blob using a Web Worker.
 * The hashing runs entirely off the main thread, keeping the UI responsive.
 * Falls back to main-thread streaming hash if workers are unavailable.
 * Returns a lowercase hex string (64 characters).
 */
export async function computeFileSHA256(file: Blob): Promise<string> {
  // Try Web Worker first (off main thread)
  if (typeof Worker !== 'undefined') {
    try {
      return await new Promise<string>((resolve, reject) => {
        const worker = new Worker(
          new URL('./hash-worker.ts', import.meta.url),
          { type: 'module' },
        )
        worker.onmessage = (
          e: MessageEvent<{ hash?: string; error?: string }>,
        ) => {
          worker.terminate()
          if (e.data.error) {
            reject(new Error(e.data.error))
          } else {
            resolve(e.data.hash!)
          }
        }
        worker.onerror = (err) => {
          worker.terminate()
          reject(err)
        }
        worker.postMessage({ file })
      })
    } catch {
      // Worker failed — fall through to main-thread fallback
    }
  }

  // Fallback: main-thread streaming hash
  const { computeFileSHA256Streaming } = await import('./streaming-hash')
  return computeFileSHA256Streaming(file)
}

// ── Metadata Encryption ──

/**
 * Derive a metadata encryption key from the master key using HKDF.
 *
 * Used to encrypt the Info message (file names, sizes, types) so that
 * metadata is never sent in plaintext over the P2P data channel.
 */
async function deriveMetadataKey(
  masterKey: CryptoKey,
  salt: Uint8Array,
): Promise<CryptoKey> {
  if (salt.byteLength === 0) {
    throw new Error(
      'Empty salt is not allowed — cannot derive a secure metadata key.',
    )
  }

  const hkdfKey = await getHkdfKey(masterKey)

  const encoder = new TextEncoder()
  const info = encoder.encode('file-sharing-metadata')

  return crypto.subtle.deriveKey(
    {
      name: 'HKDF',
      hash: 'SHA-256',
      salt: salt as BufferSource,
      info,
    },
    hkdfKey,
    { name: 'AES-GCM', length: KEY_LENGTH },
    false,
    ['encrypt', 'decrypt'],
  )
}

/**
 * Encrypt a JSON-serializable object using the master key's derived metadata key.
 * Returns an ArrayBuffer containing IV || ciphertext.
 */
export async function encryptMetadata(
  masterKey: CryptoKey,
  data: unknown,
  salt: Uint8Array,
): Promise<ArrayBuffer> {
  const metadataKey = await deriveMetadataKey(masterKey, salt)
  const encoder = new TextEncoder()
  let json: string
  try {
    json = JSON.stringify(data)
  } catch {
    throw new Error('Metadata is not JSON-serializable')
  }
  const plaintext = encoder.encode(json)
  if (plaintext.byteLength > 16 * 1024 * 1024) {
    throw new Error('Metadata too large (max 16MB)')
  }
  // Use slice to get an exact-sized ArrayBuffer — plaintext.buffer may be larger
  // than plaintext.byteLength on some engines (shared backing buffer)
  return encryptChunk(
    metadataKey,
    plaintext.buffer.slice(
      plaintext.byteOffset,
      plaintext.byteOffset + plaintext.byteLength,
    ),
  )
}

/**
 * Decrypt an encrypted metadata payload back into a parsed JSON object.
 */
export async function decryptMetadata(
  masterKey: CryptoKey,
  encrypted: ArrayBuffer,
  salt: Uint8Array,
): Promise<unknown> {
  const metadataKey = await deriveMetadataKey(masterKey, salt)
  const decrypted = await decryptChunk(metadataKey, encrypted)
  const decoder = new TextDecoder()
  return JSON.parse(decoder.decode(decrypted))
}

// ── Key Commitment (HMAC-SHA256) ──

/**
 * Derive a separate commitment key from the master key via HKDF.
 *
 * AES-GCM is not key-committing — an attacker who knows the key can craft a
 * different key that decrypts the same ciphertext to different plaintext.
 * HMAC-SHA256 commitment binds the derived file key to file metadata.
 *
 * Uses a distinct info string to ensure domain separation from file encryption keys.
 */
async function deriveCommitmentKey(
  masterKey: CryptoKey,
  fileName: string,
  fileIndex: number,
  salt: Uint8Array,
): Promise<CryptoKey> {
  const hkdfKey = await getHkdfKey(masterKey)
  const encoder = new TextEncoder()
  const info = encoder.encode(
    `file-sharing-commitment:${fileIndex}:${fileName}`,
  )

  return crypto.subtle.deriveKey(
    {
      name: 'HKDF',
      hash: 'SHA-256',
      salt: salt as BufferSource,
      info,
    },
    hkdfKey,
    { name: 'HMAC', hash: 'SHA-256', length: 256 },
    true, // extractable so we can use for HMAC
    ['sign', 'verify'],
  )
}

/**
 * Compute a key commitment for a file.
 *
 * Produces a 64-character hex string: HMAC-SHA256(commitmentKey, message)
 * where message = "fileName:fileSize:fileIndex:saltHex"
 *
 * This binds the encryption key to the file's metadata, preventing key substitution.
 */
export async function computeKeyCommitment(
  masterKey: CryptoKey,
  fileName: string,
  fileSize: number,
  fileIndex: number,
  salt: Uint8Array,
): Promise<string> {
  const commitmentKey = await deriveCommitmentKey(
    masterKey,
    fileName,
    fileIndex,
    salt,
  )

  const saltHex = toHex(salt)
  const encoder = new TextEncoder()
  const message = encoder.encode(
    `${fileName}:${fileSize}:${fileIndex}:${saltHex}`,
  )

  const signature = await crypto.subtle.sign('HMAC', commitmentKey, message)
  return toHex(new Uint8Array(signature))
}

/**
 * Verify a key commitment for a file.
 *
 * Returns true if the commitment matches, false otherwise.
 * Returns true (skip) if commitment is undefined (backwards compatibility).
 */
export async function verifyKeyCommitment(
  masterKey: CryptoKey,
  fileName: string,
  fileSize: number,
  fileIndex: number,
  salt: Uint8Array,
  commitment: string | undefined,
): Promise<boolean> {
  if (!commitment) {
    throw new Error(
      'Key commitment is required — the uploader must provide a commitment to verify file integrity.',
    )
  }

  const expected = await computeKeyCommitment(
    masterKey,
    fileName,
    fileSize,
    fileIndex,
    salt,
  )
  return secureCompare(expected, commitment)
}

// ── Base64url Helpers ──

function arrayBufferToBase64url(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function base64urlToArrayBuffer(base64url: string): ArrayBuffer {
  // Restore standard base64
  let base64 = base64url.replace(/-/g, '+').replace(/_/g, '/')
  // Add padding
  while (base64.length % 4 !== 0) {
    base64 += '='
  }
  let binary: string
  try {
    binary = atob(base64)
  } catch {
    throw new Error('Invalid base64url encoding in key or salt')
  }
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i)
  }
  return bytes.buffer
}
