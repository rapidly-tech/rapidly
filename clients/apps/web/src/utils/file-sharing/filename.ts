/**
 * Cross-platform filename sanitization.
 *
 * Shared between:
 * - messages.ts (Zod safeFileName transform — normalizes on parse)
 * - fs.ts (getFileName — normalizes at the source)
 *
 * This ensures the uploader and downloader always agree on filenames.
 */

/** Characters that are invalid on Windows. Replaced with underscores. */
const WINDOWS_UNSAFE_CHARS = /[<>:"|?*]/g

/**
 * Windows reserved device names (case-insensitive, with or without extensions).
 * These names cannot be used as filenames on Windows regardless of extension.
 */
const WINDOWS_RESERVED_NAMES = /^(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(\.|$)/i

/**
 * Sanitize a filename for cross-platform safety.
 *
 * - Normalizes backslashes to forward slashes
 * - Replaces Windows-unsafe characters (<>:"|?*) with underscores
 * - Prefixes Windows reserved device names (CON, AUX, etc.) with underscore
 */
export function sanitizeFileName(name: string): string {
  let sanitized = name.replace(/\\/g, '/')
  sanitized = sanitized.replace(WINDOWS_UNSAFE_CHARS, '_')
  sanitized = sanitized
    .split('/')
    .map((seg) => (WINDOWS_RESERVED_NAMES.test(seg) ? `_${seg}` : seg))
    .join('/')
  return sanitized
}
