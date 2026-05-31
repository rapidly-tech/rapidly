/**
 * Engineering-units formatter for the Markup chamber.
 *
 * Consumes the board's ``BoardScale`` (from `calibration.ts`) and
 * formats a pixel length as a real-world-unit string. When no scale
 * is set, falls back to whole-pixel rendering so the existing
 * dimensions-overlay output (e.g. "400 × 300") stays exact.
 *
 * Precision conventions:
 *   - mm: 0 decimals (millimetres are already precise enough for
 *     drawing-scale annotations)
 *   - m : 2 decimals (1cm precision)
 *   - in: 2 decimals (1/100 inch)
 *   - ft: 1 decimal (~1/8 inch). The architectural ``5'-3″`` form
 *     is gnarly to format and not needed for v1; decimal feet is
 *     the lowest-friction choice and matches what most engineers
 *     read in their drawing-package metadata.
 */

import type { BoardScale, Unit } from './calibration'

export interface UnitFormatter {
  /** Format a pixel length as a string with units. */
  format(pixels: number): string
}

/** Build a formatter that turns pixel lengths into real-world-unit
 *  strings. ``scale === null`` returns a pixel formatter so callers
 *  don't need a separate branch. */
export function makeFormatter(scale: BoardScale | null): UnitFormatter {
  if (scale === null) {
    return {
      format(pixels) {
        return `${Math.round(pixels)} px`
      },
    }
  }
  const decimals = decimalsForUnit(scale.unit)
  return {
    format(pixels) {
      const real = pixels * scale.unitsPerPixel
      return `${real.toFixed(decimals)} ${scale.unit}`
    },
  }
}

function decimalsForUnit(unit: Unit): number {
  switch (unit) {
    case 'mm':
      return 0
    case 'm':
      return 2
    case 'in':
      return 2
    case 'ft':
      return 1
  }
}
