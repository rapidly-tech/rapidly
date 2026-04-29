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
 *  Path uses ``/secret/local`` as a sentinel so a future page route
 *  can branch on it without parsing the fragment first. */
export function buildLocalSecretURL(payloadB64Url: string): string {
  return `${window.location.origin}/secret/local#${payloadB64Url}`
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
