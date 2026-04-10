/**
 * Shared hex encoding utility for the file sharing module.
 */

/**
 * Convert raw bytes to a lowercase hex string.
 */
export function toHex(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
}
