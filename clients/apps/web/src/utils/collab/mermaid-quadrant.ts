/**
 * Quadrant-chart subset of Mermaid → Collab elements.
 *
 * Parses the Mermaid quadrantChart syntax — title + x-axis + y-axis
 * label endpoints, the four quadrant labels, and data points with
 * ``[x, y]`` coordinates in the 0..1 unit square — and lays it out
 * as a 2×2 grid with axes, quadrant labels, and labelled data
 * dots.
 *
 * What we handle
 * --------------
 *   ``quadrantChart``                            — header
 *   ``title Reach vs Effort``                    — title
 *   ``x-axis Low Reach --> High Reach``          — x label endpoints
 *   ``y-axis Low Effort --> High Effort``        — y label endpoints
 *   ``quadrant-1 We should do``                  — top-right label
 *   ``quadrant-2 Maybe``                         — top-left label
 *   ``quadrant-3 Don't bother``                  — bottom-left label
 *   ``quadrant-4 Do it now``                     — bottom-right label
 *   ``Campaign A: [0.3, 0.6]``                   — data point (x, y)
 *   ``%% comment`` lines                         — skipped
 *
 * Out of scope (decays to "ignored line"):
 *   - ``classDef`` styling
 *   - ``%%{init: {...}}%%`` config
 *   - point styling (``radius``, ``stroke-color``)
 *   - quoted point names with embedded colons
 */

import type { CreateElementInput } from './element-store'

export interface QuadrantPoint {
  label: string
  x: number
  y: number
}

export interface QuadrantChart {
  title: string
  /** ``xAxisStart`` is the leftmost label, ``xAxisEnd`` the rightmost.
   *  Either may be empty when only one endpoint is declared. */
  xAxisStart: string
  xAxisEnd: string
  yAxisStart: string
  yAxisEnd: string
  /** Index 0..3 corresponds to Mermaid's quadrant-1 .. quadrant-4
   *  (top-right, top-left, bottom-left, bottom-right). */
  quadrantLabels: [string, string, string, string]
  points: QuadrantPoint[]
}

/** Parse the quadrant-chart source. Returns ``null`` when the input
 *  doesn't begin with ``quadrantChart`` so the caller can fall
 *  through to the generic "unsupported kind" message. */
export function parseQuadrantChart(source: string): QuadrantChart | null {
  const lines = source.split(/\r?\n/)
  let i = 0
  while (i < lines.length && !lines[i].trim()) i++
  const header = lines[i]?.trim() ?? ''
  if (!/^quadrantChart\b/i.test(header)) return null
  i++

  let title = ''
  let xAxisStart = ''
  let xAxisEnd = ''
  let yAxisStart = ''
  let yAxisEnd = ''
  const quadrantLabels: [string, string, string, string] = ['', '', '', '']
  const points: QuadrantPoint[] = []

  for (; i < lines.length; i++) {
    const line = lines[i].split('%%')[0].trim()
    if (line.length === 0) continue

    const titleMatch = /^title\s+(.+)$/i.exec(line)
    if (titleMatch) {
      title = titleMatch[1].trim()
      continue
    }
    // x-axis: ``x-axis Low --> High`` or ``x-axis Low``.
    const xAxisMatch = /^x-axis\s+(.+?)(?:\s*-->\s*(.+))?$/i.exec(line)
    if (xAxisMatch) {
      xAxisStart = xAxisMatch[1].trim()
      xAxisEnd = xAxisMatch[2]?.trim() ?? ''
      continue
    }
    const yAxisMatch = /^y-axis\s+(.+?)(?:\s*-->\s*(.+))?$/i.exec(line)
    if (yAxisMatch) {
      yAxisStart = yAxisMatch[1].trim()
      yAxisEnd = yAxisMatch[2]?.trim() ?? ''
      continue
    }
    // quadrant-N label.
    const quadMatch = /^quadrant-([1-4])\s+(.+)$/i.exec(line)
    if (quadMatch) {
      const idx = Number(quadMatch[1]) - 1
      quadrantLabels[idx] = quadMatch[2].trim()
      continue
    }
    // Data point: ``Label: [x, y]``.
    const pointMatch =
      /^([^:]+?)\s*:\s*\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]\s*$/.exec(
        line,
      )
    if (pointMatch) {
      points.push({
        label: pointMatch[1].trim(),
        x: Number(pointMatch[2]),
        y: Number(pointMatch[3]),
      })
      continue
    }
    // Unrecognised — silently skip.
  }

  return {
    title,
    xAxisStart,
    xAxisEnd,
    yAxisStart,
    yAxisEnd,
    quadrantLabels,
    points,
  }
}

const PLOT_SIZE = 360
const TITLE_HEIGHT = 28
const AXIS_LABEL_HEIGHT = 22
const Y_LABEL_WIDTH = 70
const POINT_RADIUS = 8

const QUADRANT_FILLS = ['#d3f9d8', '#fff3bf', '#ffe3e3', '#e7f5ff'] as const
const POINT_FILLS = ['#1971c2', '#2f9e44', '#e03131', '#9c36b5'] as const

export interface QuadrantLayoutOptions {
  originX?: number
  originY?: number
}

/** Lay out the parsed chart and emit Collab element inputs. */
export function quadrantChartToElements(
  chart: QuadrantChart,
  options: QuadrantLayoutOptions = {},
): CreateElementInput[] {
  const ox = options.originX ?? 0
  const oy = options.originY ?? 0
  const out: CreateElementInput[] = []

  // Title row.
  if (chart.title) {
    out.push({
      type: 'text',
      x: ox,
      y: oy,
      width: PLOT_SIZE + Y_LABEL_WIDTH,
      height: TITLE_HEIGHT - 6,
      text: chart.title,
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
      seed: hash('q-title'),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
  }

  const plotX0 = ox + Y_LABEL_WIDTH
  const plotY0 = oy + (chart.title ? TITLE_HEIGHT : 0)
  const plotX1 = plotX0 + PLOT_SIZE
  const plotY1 = plotY0 + PLOT_SIZE
  const halfX = plotX0 + PLOT_SIZE / 2
  const halfY = plotY0 + PLOT_SIZE / 2

  // Quadrant fill rects. Mermaid numbering: 1 = top-right, 2 = top-left,
  // 3 = bottom-left, 4 = bottom-right. Lay them out accordingly.
  const quadrantRects: Array<{
    x: number
    y: number
    label: string
    fill: string
    seed: string
  }> = [
    {
      x: halfX,
      y: plotY0,
      label: chart.quadrantLabels[0],
      fill: QUADRANT_FILLS[0],
      seed: 'q-1',
    },
    {
      x: plotX0,
      y: plotY0,
      label: chart.quadrantLabels[1],
      fill: QUADRANT_FILLS[1],
      seed: 'q-2',
    },
    {
      x: plotX0,
      y: halfY,
      label: chart.quadrantLabels[2],
      fill: QUADRANT_FILLS[2],
      seed: 'q-3',
    },
    {
      x: halfX,
      y: halfY,
      label: chart.quadrantLabels[3],
      fill: QUADRANT_FILLS[3],
      seed: 'q-4',
    },
  ]
  for (const q of quadrantRects) {
    out.push({
      type: 'rect',
      x: q.x,
      y: q.y,
      width: PLOT_SIZE / 2,
      height: PLOT_SIZE / 2,
      strokeColor: '#94a3b8',
      fillColor: q.fill,
      fillStyle: 'solid',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash(q.seed),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
      roundness: 0,
    } as CreateElementInput)
    if (q.label) {
      out.push({
        type: 'text',
        x: q.x + 8,
        y: q.y + 6,
        width: PLOT_SIZE / 2 - 16,
        height: 16,
        text: q.label,
        fontFamily: 'sans',
        fontSize: 12,
        textAlign: 'center',
        fontWeight: 'bold',
        strokeColor: '#475569',
        fillColor: 'transparent',
        fillStyle: 'none',
        strokeWidth: 1,
        strokeStyle: 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash(q.seed + '-label'),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
    }
  }

  // X axis labels at the bottom — start on the left, end on the right.
  if (chart.xAxisStart) {
    out.push(
      makeAxisLabel(
        chart.xAxisStart,
        plotX0,
        plotY1 + 4,
        PLOT_SIZE / 2,
        'left',
        'q-x-start',
      ),
    )
  }
  if (chart.xAxisEnd) {
    out.push(
      makeAxisLabel(
        chart.xAxisEnd,
        halfX,
        plotY1 + 4,
        PLOT_SIZE / 2,
        'right',
        'q-x-end',
      ),
    )
  }
  // Y axis labels in the left gutter — start at the bottom, end at the top.
  if (chart.yAxisStart) {
    out.push(
      makeAxisLabel(
        chart.yAxisStart,
        ox,
        plotY1 - 18,
        Y_LABEL_WIDTH - 6,
        'right',
        'q-y-start',
      ),
    )
  }
  if (chart.yAxisEnd) {
    out.push(
      makeAxisLabel(
        chart.yAxisEnd,
        ox,
        plotY0 + 4,
        Y_LABEL_WIDTH - 6,
        'right',
        'q-y-end',
      ),
    )
  }

  // Data points + labels. (x, y) maps from the 0..1 unit square to
  // the plot rectangle, with the y axis inverted so y=1 lands at
  // the top.
  chart.points.forEach((p, idx) => {
    const px = plotX0 + Math.max(0, Math.min(1, p.x)) * PLOT_SIZE
    const py = plotY1 - Math.max(0, Math.min(1, p.y)) * PLOT_SIZE
    const colour = POINT_FILLS[idx % POINT_FILLS.length]
    out.push({
      type: 'ellipse',
      x: px - POINT_RADIUS,
      y: py - POINT_RADIUS,
      width: POINT_RADIUS * 2,
      height: POINT_RADIUS * 2,
      strokeColor: colour,
      fillColor: colour,
      fillStyle: 'solid',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash(`q-point-${idx}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
    out.push({
      type: 'text',
      x: px + POINT_RADIUS + 4,
      y: py - 9,
      width: 140,
      height: 16,
      text: p.label,
      fontFamily: 'sans',
      fontSize: 12,
      textAlign: 'left',
      strokeColor: '#1e1e1e',
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash(`q-point-label-${idx}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
  })

  // We use plotX1 above and below the loop indirectly; explicitly
  // touch it here so the variable isn't flagged as unused.
  void plotX1

  return out
}

function makeAxisLabel(
  text: string,
  x: number,
  y: number,
  width: number,
  align: 'left' | 'right',
  seed: string,
): CreateElementInput {
  return {
    type: 'text',
    x,
    y,
    width,
    height: AXIS_LABEL_HEIGHT - 6,
    text,
    fontFamily: 'sans',
    fontSize: 11,
    textAlign: align,
    strokeColor: '#475569',
    fillColor: 'transparent',
    fillStyle: 'none',
    strokeWidth: 1,
    strokeStyle: 'solid',
    roughness: 0,
    opacity: 100,
    seed: hash(seed),
    version: 0,
    locked: false,
    angle: 0,
    zIndex: 0,
    groupIds: [],
  } as CreateElementInput
}

function hash(s: string): number {
  let h = 5381
  for (let i = 0; i < s.length; i++) h = (h * 33) ^ s.charCodeAt(i)
  return h >>> 0
}
