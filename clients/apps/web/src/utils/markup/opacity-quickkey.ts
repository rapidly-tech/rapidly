/**
 * Opacity quick-keys — Figma-style "press a digit to set the
 * selection's opacity to that decile" pass.
 *
 * Mapping
 * -------
 *   1  → 10
 *   2  → 20
 *   3  → 30
 *   4  → 40
 *   5  → 50
 *   6  → 60
 *   7  → 70
 *   8  → 80
 *   9  → 90
 *   0  → 100   (matches Figma — 0 reads as "max" in muscle memory)
 *
 * Anything else returns ``null`` so the keyboard handler can fall
 * through to the next branch instead of silently swallowing the key.
 *
 * Pure / testable. The keydown wiring lives in
 * ``CollabWhiteboard.tsx``; this module owns only the digit→opacity
 * mapping so the test can lock the ladder without spinning up
 * React.
 */

/** Return the opacity (0..100) implied by a digit, or ``null`` when
 *  the input isn't a single decimal digit. ``'0'`` maps to 100 to
 *  match Figma — pressing 0 reads as "make it solid", not "make it
 *  invisible". */
export function digitToOpacity(key: string): number | null {
  if (typeof key !== 'string' || key.length !== 1) return null
  if (!/^[0-9]$/.test(key)) return null
  if (key === '0') return 100
  return Number(key) * 10
}
