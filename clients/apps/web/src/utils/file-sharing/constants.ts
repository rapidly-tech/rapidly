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

// ── Transport constants ──

/** Backpressure threshold — pause sending when buffered data exceeds this (4 MB). */
export const BUFFER_THRESHOLD = 4 * 1024 * 1024

/** Maximum header size in binary frames (64 KB — matches server MAX_SIGNALING_MESSAGE_SIZE). */
export const MAX_HEADER_SIZE = 64 * 1024

/** Maximum total frame size (64 MB — prevents memory exhaustion from malicious peers). */
export const MAX_FRAME_SIZE = 64 * 1024 * 1024

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
