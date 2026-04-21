/**
 * SVG export for the Collab v2 whiteboard.
 *
 * Serialises the scene as a vector-format SVG document — good for
 * scaling without aliasing, editing in Illustrator / Figma / Inkscape,
 * and embedding in design docs. Complements the PNG rasteriser from
 * Phase 14a.
 *
 * Rough-style caveat
 * ------------------
 * Rough / hand-drawn strokes aren't reproduced in SVG output — the
 * jitter is a render-time effect of ``shapes/`` adapters using a
 * seeded PRNG, and replicating that in static SVG paths would need a
 * parallel implementation. For now, SVG exports paint clean / straight
 * equivalents of every shape regardless of the element's roughness.
 * Callers who need pixel-exact output should use ``exportToPNG`` from
 * ``export.ts``.
 *
 * Escape discipline
 * -----------------
 * Text content and any attribute that could hold user input is passed
 * through ``escapeXml`` / ``escapeAttr`` before being placed in the
 * output — ``<``, ``>``, ``&``, ``""``, ``'``. Shared canvas is a cross-
 * user surface; an unescaped ``</svg>`` inside a text element would
 * truncate the file.
 */

import type { CollabElement } from './elements'
import { computeBounds } from './export'

export interface ExportSVGOptions {
  /** World units of padding around the scene bounds. Default 24,
   *  matches ``exportToPNG`` so both formats have the same framing. */
  padding?: number
  /** Background fill. ``'transparent'`` or ``null`` omits the
   *  background rectangle so the SVG composites over whatever it's
   *  embedded in. Default ``'#ffffff'``. */
  background?: string | null
}

const DEFAULT_PADDING = 24
const DEFAULT_BACKGROUND = '#ffffff'

/** Produce an SVG document as a string covering every element in the
 *  input list. Always returns a valid document — empty input yields a
 *  zero-sized ``<svg>`` rather than throwing, so callers can dump
 *  whatever they have without branching. */
export function exportToSVG(
  elements: readonly CollabElement[],
  options: ExportSVGOptions = {},
): string {
  const bounds = computeBounds(elements)
  const padding = options.padding ?? DEFAULT_PADDING
  // Treat ``null`` as ""explicitly no background"" — ``??`` would
  // coerce it back to the default, so branch on ``undefined``
  // specifically.
  const background =
    options.background === undefined ? DEFAULT_BACKGROUND : options.background

  if (!bounds) return emptyDocument()

  const vbX = bounds.x - padding
  const vbY = bounds.y - padding
  const vbW = bounds.width + padding * 2
  const vbH = bounds.height + padding * 2

  const bgRect =
    background !== null && background !== 'transparent'
      ? `<rect x="${vbX}" y="${vbY}" width="${vbW}" height="${vbH}" fill="${escapeAttr(background)}"/>`
      : ''

  const body = elements
    .map((el) => serialiseElement(el))
    .filter((s): s is string => s !== null)
    .join('\n  ')

  // Arrowhead marker — one per doc, referenced by any arrow. Cheaper
  // than inline-drawing the triangle on every arrow and lets downstream
  // editors recognise it as a marker.
  const defs = `<defs>
    <marker id="collab-arrow-head" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
      <path d="M0,0 L8,4 L0,8 z" fill="currentColor"/>
    </marker>
  </defs>`

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vbX} ${vbY} ${vbW} ${vbH}" width="${vbW}" height="${vbH}">
  ${defs}
  ${bgRect}
  ${body}
</svg>`
}

// ── Element serialisers ──────────────────────────────────────────────

function serialiseElement(el: CollabElement): string | null {
  // Common wrapper: translate to (x, y), rotate about centre if angle
  // set, apply opacity. Individual shapes draw into element-local
  // coords (origin at top-left).
  const cx = el.width / 2
  const cy = el.height / 2
  const transform =
    el.angle !== 0
      ? `translate(${el.x} ${el.y}) rotate(${(el.angle * 180) / Math.PI} ${cx} ${cy})`
      : `translate(${el.x} ${el.y})`
  const opacity =
    typeof el.opacity === 'number' && el.opacity !== 100
      ? ` opacity="${el.opacity / 100}"`
      : ''

  const inner = innerFor(el)
  if (!inner) return null
  return `<g transform="${transform}"${opacity}>${inner}</g>`
}

function innerFor(el: CollabElement): string | null {
  switch (el.type) {
    case 'rect':
      return rectSvg(el)
    case 'ellipse':
      return ellipseSvg(el)
    case 'diamond':
      return diamondSvg(el)
    case 'line':
      return lineSvg(el)
    case 'arrow':
      return arrowSvg(el)
    case 'freedraw':
      return freedrawSvg(el)
    case 'text':
      return textSvg(el)
    case 'sticky':
      return stickySvg(el)
    case 'image':
      return imageSvg(el)
    default:
      // Frame / embed not yet wired.
      return null
  }
}

function rectSvg(el: CollabElement & { roundness?: number }): string {
  const r = Math.max(0, el.roundness ?? 0)
  return `<rect width="${el.width}" height="${el.height}"${r > 0 ? ` rx="${r}" ry="${r}"` : ''} ${strokeFill(el)}/>`
}

function ellipseSvg(el: CollabElement): string {
  const rx = el.width / 2
  const ry = el.height / 2
  return `<ellipse cx="${rx}" cy="${ry}" rx="${rx}" ry="${ry}" ${strokeFill(el)}/>`
}

function diamondSvg(el: CollabElement): string {
  const w = el.width
  const h = el.height
  const pts = `${w / 2},0 ${w},${h / 2} ${w / 2},${h} 0,${h / 2}`
  return `<polygon points="${pts}" ${strokeFill(el)}/>`
}

function lineSvg(el: CollabElement & { points?: number[] }): string {
  const pts = formatPoints(el.points ?? [])
  return `<polyline points="${pts}" ${stroke(el)} fill="none"/>`
}

function arrowSvg(el: CollabElement & { points?: number[] }): string {
  const pts = formatPoints(el.points ?? [])
  return `<polyline points="${pts}" ${stroke(el)} fill="none" marker-end="url(#collab-arrow-head)" color="${escapeAttr(el.strokeColor)}"/>`
}

function freedrawSvg(el: CollabElement & { points?: number[] }): string {
  // FreeDraw stores [x0,y0,pressure0, x1,y1,pressure1, ...] — pressure
  // is the third in each triplet; SVG polyline doesn't carry it, so
  // we reduce to x/y pairs. Good-enough for ""vector export"".
  const raw = el.points ?? []
  const out: string[] = []
  for (let i = 0; i + 1 < raw.length; i += 3) {
    out.push(`${raw[i]},${raw[i + 1]}`)
  }
  return `<polyline points="${out.join(' ')}" ${stroke(el)} fill="none" stroke-linecap="round" stroke-linejoin="round"/>`
}

function textSvg(
  el: CollabElement & { text?: string; fontSize?: number },
): string {
  const fontSize = el.fontSize ?? 20
  return `<text x="0" y="${fontSize}" font-family="system-ui, sans-serif" font-size="${fontSize}" fill="${escapeAttr(el.strokeColor)}">${escapeXml(el.text ?? '')}</text>`
}

function stickySvg(
  el: CollabElement & { text?: string; fontSize?: number },
): string {
  const fontSize = el.fontSize ?? 16
  const padding = 8
  const rect = `<rect width="${el.width}" height="${el.height}" rx="6" ry="6" fill="${escapeAttr(el.fillColor || '#fde68a')}" stroke="${escapeAttr(el.strokeColor)}" stroke-width="${el.strokeWidth ?? 1}"/>`
  const text = `<text x="${padding}" y="${padding + fontSize}" font-family="system-ui, sans-serif" font-size="${fontSize}" fill="${escapeAttr(el.strokeColor)}">${escapeXml(el.text ?? '')}</text>`
  return rect + text
}

function imageSvg(el: CollabElement & { thumbnailDataUrl?: string }): string {
  if (!el.thumbnailDataUrl)
    return `<rect width="${el.width}" height="${el.height}" fill="#cbd5e1"/>`
  return `<image width="${el.width}" height="${el.height}" href="${escapeAttr(el.thumbnailDataUrl)}" preserveAspectRatio="none"/>`
}

// ── Attribute helpers ────────────────────────────────────────────────

function strokeFill(el: CollabElement): string {
  const stroke = `stroke="${escapeAttr(el.strokeColor)}" stroke-width="${el.strokeWidth ?? 1}"`
  const fill =
    el.fillColor && el.fillColor !== 'transparent' && el.fillStyle !== 'none'
      ? `fill="${escapeAttr(el.fillColor)}"`
      : 'fill="none"'
  const dash = strokeDash(el.strokeStyle)
  return `${stroke} ${fill}${dash}`
}

function stroke(el: CollabElement): string {
  const base = `stroke="${escapeAttr(el.strokeColor)}" stroke-width="${el.strokeWidth ?? 1}"`
  return `${base}${strokeDash(el.strokeStyle)}`
}

function strokeDash(style: string | undefined): string {
  if (style === 'dashed') return ` stroke-dasharray="8 4"`
  if (style === 'dotted') return ` stroke-dasharray="1 4"`
  return ''
}

function formatPoints(pts: readonly number[]): string {
  const out: string[] = []
  for (let i = 0; i + 1 < pts.length; i += 2) {
    out.push(`${pts[i]},${pts[i + 1]}`)
  }
  return out.join(' ')
}

// ── Escaping ─────────────────────────────────────────────────────────

const XML_ESCAPES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&apos;',
}

export function escapeXml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => XML_ESCAPES[c])
}

export function escapeAttr(s: string): string {
  return escapeXml(s)
}

function emptyDocument(): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1" width="1" height="1"></svg>`
}
