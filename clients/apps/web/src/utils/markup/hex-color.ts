/**
 * Hex-colour parsing — accept what users actually type and return a
 * canonical 6-digit ``#rrggbb`` so the rest of the codebase can treat
 * colours as opaque strings without re-running validation.
 *
 * Accepts
 * -------
 *   ``#abc``       → ``#aabbcc``     (3-digit shorthand, expanded)
 *   ``#abcdef``    → ``#abcdef``     (already canonical)
 *   ``abcdef``     → ``#abcdef``     (missing leading hash)
 *   ``ABCDEF``     → ``#abcdef``     (lowercased)
 *   ``  #abc  ``   → ``#aabbcc``     (whitespace trimmed)
 *
 * Rejects (returns ``null``)
 * --------------------------
 *   anything containing non-hex characters, the empty string, four-
 *   digit / five-digit / seven-digit lengths, and 8-digit rrggbbaa
 *   (the rest of our palette doesn't carry alpha — adding it later
 *   would be a separate plumbing change so we'd rather fail loud now).
 */

/** Canonicalise a free-form hex string. Returns ``null`` when the
 *  input doesn't parse as a 3- or 6-digit hex colour. */
export function normaliseHex(input: string): string | null {
  if (typeof input !== 'string') return null
  const trimmed = input.trim()
  if (trimmed.length === 0) return null
  const withoutHash = trimmed.startsWith('#') ? trimmed.slice(1) : trimmed
  if (!/^[0-9a-fA-F]+$/.test(withoutHash)) return null
  if (withoutHash.length === 3) {
    const [r, g, b] = withoutHash.toLowerCase().split('')
    return `#${r}${r}${g}${g}${b}${b}`
  }
  if (withoutHash.length === 6) {
    return `#${withoutHash.toLowerCase()}`
  }
  return null
}

/** Predicate version. Used by UI buttons that gate "apply" on
 *  validity. */
export function isValidHex(input: string): boolean {
  return normaliseHex(input) !== null
}
