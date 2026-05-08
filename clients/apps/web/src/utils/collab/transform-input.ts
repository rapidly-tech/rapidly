/**
 * Transform-input parsing — shared between the four W / H / X / Y
 * fields in the properties panel and any future numeric inputs that
 * touch element geometry.
 *
 * The job of this module is to take what users actually type into a
 * numeric field (with all the messiness that implies — leading
 * spaces, commas instead of dots in some locales, ``-`` mid-typing,
 * empty strings while editing) and decide whether it parses to a
 * usable value. The UI uses ``parseDimension`` to gate "apply" on
 * validity so an in-progress keystroke doesn't write garbage.
 */

/** Parse a free-form numeric input. Returns the number when the
 *  input is finite and inside the optional range; ``null`` otherwise.
 *
 *  Accepts:
 *    - leading + trailing whitespace
 *    - commas as the decimal separator (``1,5`` → ``1.5``)
 *    - leading ``+`` (``+10`` → ``10``)
 *    - integers and decimals
 *
 *  Rejects:
 *    - empty / whitespace-only strings
 *    - ``NaN`` / ``Infinity`` / ``-Infinity``
 *    - values outside ``[min, max]`` when supplied (each side
 *      independent — pass ``min: 1`` for size fields, leave ``max``
 *      undefined for "unbounded above") */
export function parseDimension(
  raw: string,
  bounds: { min?: number; max?: number } = {},
): number | null {
  if (typeof raw !== 'string') return null
  const trimmed = raw.trim().replace(',', '.')
  if (trimmed.length === 0) return null
  const value = Number(trimmed)
  if (!Number.isFinite(value)) return null
  if (bounds.min !== undefined && value < bounds.min) return null
  if (bounds.max !== undefined && value > bounds.max) return null
  return value
}

/** Format a numeric value for display in an input field. Drops
 *  trailing zeros so ``10`` shows as ``10`` instead of ``10.0`` and
 *  rounds to ``decimals`` places (default 2 — sub-pixel precision
 *  is rarely useful for whiteboard work). Returns the empty string
 *  for null / NaN / undefined so the input clears cleanly. */
export function formatDimension(
  value: number | null | undefined,
  decimals = 2,
): string {
  if (value === null || value === undefined) return ''
  if (!Number.isFinite(value)) return ''
  // Round, then strip trailing zeros via Number-roundtrip.
  const rounded = Number(value.toFixed(decimals))
  return String(rounded)
}
