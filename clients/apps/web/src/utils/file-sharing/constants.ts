/**
 * Shared constants for the file sharing module.
 *
 * Centralizes URL paths, thresholds, and other magic strings that were
 * previously scattered across multiple files.
 */

/** Base path for file sharing API calls. */
export const FILE_SHARING_API = '/api/file-sharing'

/** WebSocket signaling path prefix (append /{slug}). */
export const FILE_SHARING_SIGNAL_PATH = '/api/file-sharing/signal'

/** Path for the "reported" redirect page. */
export const REPORTED_PAGE = '/reported'

/** ZIP64 threshold — use ZIP64 structures when values reach this. */
export const ZIP64_THRESHOLD = 0xfffffffe

/** ZIP64 max file count threshold for ZIP32 EOCD (uint16 max). */
export const ZIP64_COUNT_THRESHOLD = 0xfffe

/** Large file warning threshold (100 MB). */
export const LARGE_FILE_THRESHOLD = 100 * 1024 * 1024

/** Very large file warning threshold (1 GB). */
export const VERY_LARGE_FILE_THRESHOLD = 1024 * 1024 * 1024

// Transport constants (BUFFER_THRESHOLD, MAX_FRAME_SIZE, MAX_HEADER_SIZE)
// moved to utils/p2p/constants.ts in PR 2 — they govern the P2P transport
// layer, not any file-sharing-specific behaviour.

// ── Formatting ──

/** Format a byte count into a human-readable string (e.g. "1.5 MB"). */
export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.min(
    Math.floor(Math.log(bytes) / Math.log(k)),
    sizes.length - 1,
  )
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

// --- Hash route builders ---
// These mirror the patterns parsed by url-parser.ts parseHash()

/** Build a file-sharing download URL: /#/d/{slug}/k/{key}/s/{salt} */
export function buildFileShareURL(
  slug: string,
  exportedKey: string,
  exportedSalt: string,
): string {
  return `${window.location.origin}/#/d/${slug}/k/${exportedKey}/s/${exportedSalt}`
}

/** Build a secret share URL: /#/s/{uuid} or /#/s/{uuid}/{password} */
export function buildSecretURL(uuid: string, password?: string): string {
  const base = `${window.location.origin}/#/s/${uuid}`
  return password ? `${base}/${password}` : base
}

/** Build a no-server (""local"") secret URL where the secret rides in
 *  the URL fragment itself. The server never sees it — fragments are
 *  not sent in HTTP requests, mirroring the file-sharing model where
 *  payload data never touches the server.
 *
 *  Path uses ``/secret/local`` — handled by ``/secret/[key]`` with the
 *  ``local`` sentinel branch in ``SecretClient``. */
export function buildLocalSecretURL(payloadB64Url: string): string {
  return `${window.location.origin}/secret/local#${payloadB64Url}`
}

/** Versioned envelope for no-server secrets. Lets us carry title /
 *  expiry / encryption flag alongside the payload without sending
 *  anything to the server (the whole envelope rides in the URL
 *  fragment).
 *
 *  ``v: 1`` is the parser sentinel — older raw-base64 fragments from
 *  before envelopes existed parse without ``v`` and are handled by
 *  the receiver's backward-compat fallback. */
export interface LocalSecretEnvelope {
  v: 1
  /** base64url of the payload bytes. When ``encrypted`` is true the
   *  payload bytes are an OpenPGP armored ciphertext; otherwise they
   *  are the plaintext UTF-8 secret. */
  secret: string
  /** Optional human-readable label shown above the reveal button. */
  title?: string
  /** Unix milliseconds. Soft client-enforced — there's no server to
   *  delete the link, so this only stops a well-behaved recipient
   *  from viewing past the deadline. */
  expires_at?: number
  /** True when ``secret`` is an OpenPGP armored ciphertext that needs
   *  the recipient to enter a password to decrypt. */
  encrypted?: boolean
}

/** Encode a no-server envelope into a fragment-safe base64url string. */
export function encodeLocalSecretEnvelope(env: LocalSecretEnvelope): string {
  return toBase64Url(JSON.stringify(env))
}

/** Decode a fragment back into an envelope. Returns ``null`` if the
 *  fragment isn't a v1 envelope — the receiver falls back to treating
 *  the fragment as a raw base64 plaintext (backward compat with
 *  links generated before envelopes existed). */
export function decodeLocalSecretEnvelope(
  fragment: string,
): LocalSecretEnvelope | null {
  let json: string
  try {
    json = fromBase64Url(fragment)
  } catch {
    return null
  }
  let parsed: unknown
  try {
    parsed = JSON.parse(json)
  } catch {
    return null
  }
  if (
    !parsed ||
    typeof parsed !== 'object' ||
    (parsed as { v?: unknown }).v !== 1 ||
    typeof (parsed as { secret?: unknown }).secret !== 'string'
  ) {
    return null
  }
  return parsed as LocalSecretEnvelope
}

/** Encode a UTF-8 string to base64url so it survives the URL fragment
 *  intact. Stripped padding + ``-`` / ``_`` make the result safe to
 *  paste into clipboards, QR codes, and chat clients. */
export function toBase64Url(input: string): string {
  if (typeof window === 'undefined') {
    return Buffer.from(input, 'utf8')
      .toString('base64')
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/, '')
  }
  // Browsers — encode UTF-8 bytes via TextEncoder so non-ASCII secrets
  // (passwords with emoji, anything multi-byte) round-trip correctly.
  const bytes = new TextEncoder().encode(input)
  let binary = ''
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

/** Inverse of ``toBase64Url``. Throws on malformed input — the caller
 *  surfaces a friendly error to the recipient. */
export function fromBase64Url(input: string): string {
  // Restore padding + standard chars so atob accepts it.
  let b64 = input.replace(/-/g, '+').replace(/_/g, '/')
  while (b64.length % 4 !== 0) b64 += '='
  if (typeof window === 'undefined') {
    return Buffer.from(b64, 'base64').toString('utf8')
  }
  const binary = atob(b64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return new TextDecoder().decode(bytes)
}
