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

export interface ExportStrokesToSvgOptions {
  /** Background colour. ``null`` / ``'transparent'`` omits the fill
   *  rect so the SVG composites over its host background. Default
   *  ``'#ffffff'`` matches the live canvas's paper-white. */
  background?: string | null
}

const DEFAULT_SVG_BACKGROUND = '#ffffff'

/** Serialise the committed strokes as a standalone SVG document.
 *  One ``<polyline>`` per stroke in the stroke's own hue; fixed
 *  viewBox matching the canvas dimensions so the export loads at
 *  identity scale in any SVG viewer. Pure — caller wraps in a Blob
 *  when ready to download. */
export function exportStrokesToSvg(
  strokes: readonly Stroke[],
  dimensions: { width: number; height: number },
  options: ExportStrokesToSvgOptions = {},
): string {
  const { width, height } = dimensions
  const background =
    options.background === undefined
      ? DEFAULT_SVG_BACKGROUND
      : options.background
  const bgRect =
    background !== null && background !== 'transparent'
      ? `<rect width="${width}" height="${height}" fill="${escapeAttr(background)}"/>`
      : ''
  const body = strokes
    .map(strokeToPolyline)
    .filter((s) => s !== '')
    .join('\n  ')
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}">
  ${bgRect}
  ${body}
</svg>`
}

function strokeToPolyline(s: Stroke): string {
  // A single-point ""stroke"" is uncommon but survive if it happens —
  // a polyline with < 2 points renders nothing, so emit a dot circle
  // instead so tap-without-drag still leaves a mark.
  if (s.pts.length < 4) {
    if (s.pts.length < 2) return ''
    const [x, y] = s.pts
    return `<circle cx="${n(x)}" cy="${n(y)}" r="${n(s.w / 2)}" fill="hsl(${n(s.hue)} 70% 50%)"/>`
  }
  const coords: string[] = []
  for (let i = 0; i + 1 < s.pts.length; i += 2) {
    coords.push(`${n(s.pts[i])},${n(s.pts[i + 1])}`)
  }
  return `<polyline points="${coords.join(' ')}" stroke="hsl(${n(s.hue)} 70% 50%)" stroke-width="${n(s.w)}" stroke-linecap="round" stroke-linejoin="round" fill="none"/>`
}

/** Round to 2 decimal places — enough for crisp SVG at every zoom,
 *  small enough to keep the output compact. */
function n(v: number): number {
  return Math.round(v * 100) / 100
}

const XML_ESCAPES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&apos;',
}

function escapeAttr(s: string): string {
  return s.replace(/[&<>"']/g, (c) => XML_ESCAPES[c])
}
