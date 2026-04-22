/**
 * Chamber stopgap export.
 *
 * The Phase 14 exporter in ``export.ts`` targets the Phase 3-27
 * whiteboard element model (``CollabElement[]``). The chamber
 * stopgap's ``CollabCanvas`` uses a different model — ``Stroke[]``
 * committed to a ``Y.Array`` — so we need a parallel, smaller
 * exporter matched to *its* data shape.
 *
 * Two formats:
 *  - **PNG** — ``HTMLCanvasElement.toBlob`` on the live canvas. No
 *    re-render needed: the canvas is already the source of truth for
 *    the pixel output.
 *  - **JSON** — versioned envelope around the committed ``Stroke[]``
 *    so a future import path can restore a scene without reverse-
 *    engineering the old shape.
 *
 * Kept out of the Phase 14 ``export.ts`` so that module stays clean
 * for the real whiteboard. When the stopgap gets replaced, delete
 * this module rather than migrating the logic.
 */

import type { Stroke } from './strokes'

/** Versioned envelope around the committed strokes. ``schema`` is
 *  distinct from the Phase 14 ``rapidly-collab-v1`` marker so a
 *  stopgap JSON export can't be accidentally fed into the real
 *  whiteboard's JSON importer (and vice versa). */
export const CHAMBER_EXPORT_SCHEMA = 'rapidly-collab-strokes-v1' as const

export interface ChamberStrokesExport {
  schema: typeof CHAMBER_EXPORT_SCHEMA
  version: 1
  /** Canvas dimensions at the time of export — the stopgap's canvas
   *  is a fixed size, but recording it lets an import path validate. */
  width: number
  height: number
  strokes: Stroke[]
}

/** Wrap the ``Stroke[]`` for download. Clones by value so later edits
 *  to the shared Y.Array don't bleed into an already-saved payload. */
export function exportStrokesToJson(
  strokes: readonly Stroke[],
  dimensions: { width: number; height: number },
): ChamberStrokesExport {
  return {
    schema: CHAMBER_EXPORT_SCHEMA,
    version: 1,
    width: dimensions.width,
    height: dimensions.height,
    strokes: strokes.map((s) => ({
      by: s.by,
      pts: s.pts.slice(),
      hue: s.hue,
      w: s.w,
    })),
  }
}

/** ``canvas.toBlob`` wrapped in a Promise. Resolves ``null`` when the
 *  browser can't produce a blob (unusual — typically means the canvas
 *  is tainted). */
export function exportCanvasToPng(
  canvas: HTMLCanvasElement,
): Promise<Blob | null> {
  return new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(blob), 'image/png')
  })
}
