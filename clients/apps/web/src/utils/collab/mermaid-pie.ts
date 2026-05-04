/**
 * Pie-chart subset of Mermaid → Collab elements.
 *
 * Parses the simple Mermaid pie syntax — optional title + ``"Label"
 * : value`` lines — and emits a circle outline with radial dividers
 * showing the proportional split, plus a colour-coded legend
 * underneath. We don't have a filled-wedge element type, so the
 * legend carries the colour-to-label mapping while the radial
 * dividers carry the visual proportions; together they communicate
 * the same information a filled pie would.
 *
 * What we handle
 * --------------
 *   ``pie [showData]``                  — header
 *   ``pie title My Chart``              — title on the same line
 *   ``title My Chart``                  — title on its own line
 *   ``"Slice A" : 40``                  — slice with value
 *   ``Slice A : 40``                    — slice without quotes
 *   ``%% comment`` lines                — skipped
 *
 * Out of scope (decays to "ignored line"):
 *   - per-slice colour overrides (``pie classDef`` blocks)
 *   - ``%%{init: {...}}%%`` config blocks
 */

import type { CreateElementInput } from './element-store'

export interface PieSlice {
  label: string
  value: number
}

export interface PieDiagram {
  title: string
  /** Whether the upstream ``showData`` flag was present. The renderer
   *  always shows numeric values + percentages in the legend, but
   *  the field is recorded so a future renderer can hide them when
   *  the flag is absent. */
  showData: boolean
  slices: PieSlice[]
}

/** Parse the pie source. Returns ``null`` when the input doesn't
 *  begin with ``pie`` so the caller can fall through to the generic
 *  "unsupported kind" message. */
export function parsePie(source: string): PieDiagram | null {
  const lines = source.split(/\r?\n/)
  let i = 0
  while (i < lines.length && !lines[i].trim()) i++
  const header = lines[i]?.trim() ?? ''
  const headerMatch = /^pie(?:\s+(showData))?(?:\s+title\s+(.+))?$/i.exec(
    header,
  )
  if (!headerMatch) return null
  i++

  const showData = headerMatch[1] !== undefined
  let title = headerMatch[2]?.trim() ?? ''
  const slices: PieSlice[] = []

  for (; i < lines.length; i++) {
    const line = lines[i].split('%%')[0].trim()
    if (line.length === 0) continue

    // Stand-alone title line.
    const titleMatch = /^title\s+(.+)$/i.exec(line)
    if (titleMatch) {
      title = titleMatch[1].trim()
      continue
    }

    // ``"Label" : 40`` or ``Label : 40`` — value must be numeric.
    // Negative or zero values are accepted and rendered (a 0-value
    // slice gets a 0° wedge — invisible but the legend still
    // surfaces it).
    const sliceQuoted = /^"([^"]+)"\s*:\s*(-?\d+(?:\.\d+)?)$/.exec(line)
    if (sliceQuoted) {
      slices.push({
        label: sliceQuoted[1],
        value: Number(sliceQuoted[2]),
      })
      continue
    }
    const sliceBare = /^([^:]+?)\s*:\s*(-?\d+(?:\.\d+)?)$/.exec(line)
    if (sliceBare) {
      slices.push({
        label: sliceBare[1].trim(),
        value: Number(sliceBare[2]),
      })
      continue
    }
    // Unrecognised line — silently skip.
  }

  return { title, showData, slices }
}

const SWATCH_PALETTE = [
  '#a5d8ff',
  '#ffec99',
  '#b2f2bb',
  '#ffc9c9',
  '#e0a9f0',
  '#fcc2d7',
  '#c0eb75',
  '#ffd8a8',
  '#a5fbe1',
  '#bac8ff',
] as const

const PIE_RADIUS = 90
const PIE_DIAMETER = PIE_RADIUS * 2
const TITLE_HEIGHT = 28
const PIE_GAP_BELOW = 16
const LEGEND_ROW_HEIGHT = 22
const SWATCH_SIZE = 14

export interface PieLayoutOptions {
  originX?: number
  originY?: number
}

/** Lay the parsed pie out and emit Collab element inputs. The
 *  caller passes the result to ``store.create`` per element inside
 *  one transaction (consistent with every other Mermaid renderer in
 *  this directory). */
export function pieToElements(
  diagram: PieDiagram,
  options: PieLayoutOptions = {},
): CreateElementInput[] {
  const ox = options.originX ?? 0
  const oy = options.originY ?? 0
  const out: CreateElementInput[] = []

  // Filter slices to positive values for layout — zero-or-negative
  // contribute nothing visible, but they still appear in the legend
  // (with 0%) so the user sees them.
  const total = diagram.slices.reduce((acc, s) => acc + Math.max(0, s.value), 0)

  // Title row.
  if (diagram.title) {
    out.push({
      type: 'text',
      x: ox,
      y: oy,
      width: PIE_DIAMETER,
      height: TITLE_HEIGHT - 6,
      text: diagram.title,
      fontFamily: 'sans',
      fontSize: 16,
      textAlign: 'center',
      fontWeight: 'bold',
      strokeColor: '#1e1e1e',
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash('pie-title'),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
  }

  // Pie circle.
  const pieY = oy + (diagram.title ? TITLE_HEIGHT : 0)
  out.push({
    type: 'ellipse',
    x: ox,
    y: pieY,
    width: PIE_DIAMETER,
    height: PIE_DIAMETER,
    strokeColor: '#1e1e1e',
    fillColor: 'transparent',
    fillStyle: 'none',
    strokeWidth: 1,
    strokeStyle: 'solid',
    roughness: 0,
    opacity: 100,
    seed: hash('pie-circle'),
    version: 0,
    locked: false,
    angle: 0,
    zIndex: 0,
    groupIds: [],
  } as CreateElementInput)

  // Radial dividers — one line from the centre to the boundary at
  // each slice angle. The first divider sits at -90° (straight up,
  // 12 o'clock) and walks clockwise. We skip dividers when total is
  // 0 (no positive slices) since every divider would land at the
  // same angle and the result would be visual noise.
  const cx = ox + PIE_RADIUS
  const cy = pieY + PIE_RADIUS
  if (total > 0) {
    let cursor = -Math.PI / 2 // 12 o'clock
    diagram.slices.forEach((slice, idx) => {
      const v = Math.max(0, slice.value)
      if (v === 0) return
      // Always emit one divider at the slice's *start* — the divider
      // at 12 o'clock for the first slice is the visual entry point.
      const ex = cx + Math.cos(cursor) * PIE_RADIUS
      const ey = cy + Math.sin(cursor) * PIE_RADIUS
      out.push({
        type: 'line',
        x: Math.min(cx, ex),
        y: Math.min(cy, ey),
        width: Math.abs(ex - cx),
        height: Math.abs(ey - cy),
        points: [
          cx - Math.min(cx, ex),
          cy - Math.min(cy, ey),
          ex - Math.min(cx, ex),
          ey - Math.min(cy, ey),
        ],
        strokeColor: '#1e1e1e',
        fillColor: 'transparent',
        fillStyle: 'none',
        strokeWidth: 1,
        strokeStyle: 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash(`pie-divider-${idx}`),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
      cursor += (v / total) * Math.PI * 2
    })
  }

  // Legend rows underneath the pie. Colour swatch + label + value +
  // percentage.
  const legendY = pieY + PIE_DIAMETER + PIE_GAP_BELOW
  diagram.slices.forEach((slice, idx) => {
    const rowY = legendY + idx * LEGEND_ROW_HEIGHT
    const colour = SWATCH_PALETTE[idx % SWATCH_PALETTE.length]
    const pct = total > 0 ? (Math.max(0, slice.value) / total) * 100 : 0
    // Swatch.
    out.push({
      type: 'rect',
      x: ox,
      y: rowY + (LEGEND_ROW_HEIGHT - SWATCH_SIZE) / 2,
      width: SWATCH_SIZE,
      height: SWATCH_SIZE,
      strokeColor: '#1e1e1e',
      fillColor: colour,
      fillStyle: 'solid',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash(`pie-swatch-${idx}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
      roundness: 2,
    } as CreateElementInput)
    // Label + value text in the same row.
    out.push({
      type: 'text',
      x: ox + SWATCH_SIZE + 8,
      y: rowY + (LEGEND_ROW_HEIGHT - 16) / 2,
      width: PIE_DIAMETER - SWATCH_SIZE - 8,
      height: 16,
      text: `${slice.label} — ${formatNumber(slice.value)} (${formatNumber(pct)}%)`,
      fontFamily: 'sans',
      fontSize: 13,
      textAlign: 'left',
      strokeColor: '#1e1e1e',
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash(`pie-label-${idx}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
  })

  return out
}

/** Drop trailing zeros after the decimal so "40.0" → "40" and
 *  "33.33" stays "33.33". Avoids the locale-specific quirks of
 *  ``toLocaleString`` so test assertions are deterministic. */
function formatNumber(n: number): string {
  if (Number.isInteger(n)) return String(n)
  return n.toFixed(2).replace(/0+$/, '').replace(/\.$/, '')
}

function hash(s: string): number {
  let h = 5381
  for (let i = 0; i < s.length; i++) h = (h * 33) ^ s.charCodeAt(i)
  return h >>> 0
}
