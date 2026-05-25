/**
 * Scale calibration for the Markup chamber.
 *
 * An engineer drops a PDF or image underlay of a drawing, then
 * calibrates it: "this line on the drawing is 5.000 m long." From
 * then on, every length the dimensions overlay reports for elements
 * on this board is in real-world units, not pixels.
 *
 * This module is the pure-math layer:
 *   - ``BoardScale`` type that the board's Yjs root map will store
 *   - ``computeUnitsPerPixel`` — turns a calibration line + a
 *     real-world length into the units-per-pixel scalar that the
 *     formatter consumes
 *
 * The tool flow (drag a line, modal asks for real length, persists
 * the scale) lives in a follow-up PR; this module is what that tool
 * will call into.
 */

export type Unit = 'mm' | 'm' | 'in' | 'ft'

export interface BoardScale {
  /** World units per canvas pixel at zoom=1. */
  unitsPerPixel: number
  /** Unit symbol stored as a hint for the formatter — the
   *  unitsPerPixel scalar is already expressed in this unit. */
  unit: Unit
}

/** Pixel-space line endpoint coordinates. The tool layer captures
 *  these in element-local pre-zoom pixels so the calibration is
 *  invariant to the viewport zoom at calibration time. */
export interface CalibrationLine {
  x1: number
  y1: number
  x2: number
  y2: number
}

/** Euclidean length in pixels. */
export function pixelLength(line: CalibrationLine): number {
  const dx = line.x2 - line.x1
  const dy = line.y2 - line.y1
  return Math.sqrt(dx * dx + dy * dy)
}

/** Compute the board scale from a calibration line and the user's
 *  declared real-world length.
 *
 *  Returns ``null`` if the line has zero length — calibrating on a
 *  degenerate line is a user error and the caller should re-prompt
 *  rather than divide by zero. */
export function computeBoardScale(
  line: CalibrationLine,
  realLength: number,
  unit: Unit,
): BoardScale | null {
  if (realLength <= 0) return null
  const pixels = pixelLength(line)
  if (pixels <= 0) return null
  return {
    unitsPerPixel: realLength / pixels,
    unit,
  }
}
