/**
 * xychart subset of Mermaid → Collab elements.
 *
 * Parses the ``xychart-beta`` syntax — title + x-axis labels + y-axis
 * range + bar / line series — and lays it out as a standard cartesian
 * chart with axes, tick marks, and the series rendered against the
 * shared x scale.
 *
 * What we handle
 * --------------
 *   ``xychart-beta``                      — header (alias: ``xychart``)
 *   ``title "Sales"``                     — title (quotes optional)
 *   ``x-axis [jan, feb, mar]``            — categorical x labels
 *   ``y-axis "Revenue" 0 --> 100``        — y label + numeric range
 *   ``bar [5, 6, 7]``                     — bar series (one bar per
 *                                           x label)
 *   ``line [5, 6, 7]``                    — line series
 *   ``%% comment`` lines                  — skipped
 *
 * Out of scope (decays to "ignored line"):
 *   - ``horizontal`` / ``vertical`` orientation flag
 *   - per-series colour overrides
 *   - numeric x-axis declarations (``x-axis 0 --> 100``)
 *   - multiple series of the same kind layered cleanly (we render
 *     each one independently — overlapping bar series will visually
 *     stack on top of each other)
 */

import type { CreateElementInput } from './element-store'

export type SeriesKind = 'bar' | 'line'

export interface XYSeries {
  kind: SeriesKind
  values: number[]
}

export interface XYChart {
  title: string
  xLabels: string[]
  yLabel: string
  yMin: number
  yMax: number
  series: XYSeries[]
}

/** Parse the xychart source. Returns ``null`` when the input doesn't
 *  begin with ``xychart`` so the caller can fall through to the
 *  generic "unsupported kind" message. */
export function parseXYChart(source: string): XYChart | null {
  const lines = source.split(/\r?\n/)
  let i = 0
  while (i < lines.length && !lines[i].trim()) i++
  const header = lines[i]?.trim() ?? ''
  if (!/^xychart(?:-beta)?\b/i.test(header)) return null
  i++

  let title = ''
  let xLabels: string[] = []
  let yLabel = ''
  let yMin = 0
  let yMax = 100
  let yRangeSet = false
  const series: XYSeries[] = []

  for (; i < lines.length; i++) {
    const line = lines[i].split('%%')[0].trim()
    if (line.length === 0) continue

    const titleMatch = /^title\s+(.+)$/i.exec(line)
    if (titleMatch) {
      title = stripQuotes(titleMatch[1])
      continue
    }
    // X axis: ``x-axis [a, b, c]`` or ``x-axis "label" [a, b, c]``.
    const xAxisMatch = /^x-axis\s+(?:"[^"]*"\s+)?\[(.+)\]\s*$/i.exec(line)
    if (xAxisMatch) {
      xLabels = xAxisMatch[1]
        .split(',')
        .map((s) => stripQuotes(s.trim()))
        .filter(Boolean)
      continue
    }
    // Y axis: ``y-axis "label" 0 --> 100`` or ``y-axis 0 --> 100``.
    const yAxisMatch =
      /^y-axis\s+(?:"([^"]*)"\s+)?(-?\d+(?:\.\d+)?)\s*-->\s*(-?\d+(?:\.\d+)?)\s*$/i.exec(
        line,
      )
    if (yAxisMatch) {
      if (yAxisMatch[1] !== undefined) yLabel = yAxisMatch[1]
      yMin = Number(yAxisMatch[2])
      yMax = Number(yAxisMatch[3])
      yRangeSet = true
      continue
    }
    // Bar / line series: ``bar [a, b, c]`` or ``line [a, b, c]``.
    const seriesMatch = /^(bar|line)\s+\[(.+)\]\s*$/i.exec(line)
    if (seriesMatch) {
      const kind = seriesMatch[1].toLowerCase() as SeriesKind
      const values = seriesMatch[2]
        .split(',')
        .map((s) => Number(s.trim()))
        .filter((n) => Number.isFinite(n))
      series.push({ kind, values })
      continue
    }
    // Unrecognised line — silently skip.
  }

  // If no y range was declared, infer one from the data so the
  // chart's bars have a sensible scale.
  if (!yRangeSet && series.length > 0) {
    const all = series.flatMap((s) => s.values)
    if (all.length > 0) {
      yMin = Math.min(0, ...all)
      yMax = Math.max(...all)
      // Add a 10% headroom so the tallest bar doesn't kiss the top
      // of the plot area.
      const span = yMax - yMin || 1
      yMax = yMax + span * 0.1
    }
  }

  return { title, xLabels, yLabel, yMin, yMax, series }
}

/** Strip a single layer of surrounding double quotes if present. */
function stripQuotes(s: string): string {
  const t = s.trim()
  if (t.startsWith('"') && t.endsWith('"')) return t.slice(1, -1)
  return t
}

const PLOT_WIDTH = 480
const PLOT_HEIGHT = 280
const TITLE_HEIGHT = 28
const X_AXIS_LABEL_HEIGHT = 22
const Y_AXIS_LABEL_WIDTH = 60
const BAR_GAP_FRACTION = 0.2

const SERIES_PALETTE = ['#1971c2', '#2f9e44', '#e03131', '#9c36b5'] as const

export interface XYLayoutOptions {
  originX?: number
  originY?: number
}

/** Lay the parsed chart out and emit Collab element inputs. */
export function xyChartToElements(
  chart: XYChart,
  options: XYLayoutOptions = {},
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
      width: PLOT_WIDTH + Y_AXIS_LABEL_WIDTH,
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
      seed: hash('xy-title'),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
  }

  const plotX0 = ox + Y_AXIS_LABEL_WIDTH
  const plotY0 = oy + (chart.title ? TITLE_HEIGHT : 0)
  const plotY1 = plotY0 + PLOT_HEIGHT

  // X axis line.
  out.push({
    type: 'line',
    x: plotX0,
    y: plotY1,
    width: PLOT_WIDTH,
    height: 0,
    points: [0, 0, PLOT_WIDTH, 0],
    strokeColor: '#475569',
    fillColor: 'transparent',
    fillStyle: 'none',
    strokeWidth: 1,
    strokeStyle: 'solid',
    roughness: 0,
    opacity: 100,
    seed: hash('xy-x-axis'),
    version: 0,
    locked: false,
    angle: 0,
    zIndex: 0,
    groupIds: [],
  } as CreateElementInput)
  // Y axis line.
  out.push({
    type: 'line',
    x: plotX0,
    y: plotY0,
    width: 0,
    height: PLOT_HEIGHT,
    points: [0, 0, 0, PLOT_HEIGHT],
    strokeColor: '#475569',
    fillColor: 'transparent',
    fillStyle: 'none',
    strokeWidth: 1,
    strokeStyle: 'solid',
    roughness: 0,
    opacity: 100,
    seed: hash('xy-y-axis'),
    version: 0,
    locked: false,
    angle: 0,
    zIndex: 0,
    groupIds: [],
  } as CreateElementInput)
  // Y axis label (rotated text would be ideal but our renderer does
  // axis-aligned text only; render it left of the plot centred
  // vertically as a single horizontal line).
  if (chart.yLabel) {
    out.push({
      type: 'text',
      x: ox,
      y: plotY0 + PLOT_HEIGHT / 2 - 9,
      width: Y_AXIS_LABEL_WIDTH - 6,
      height: 18,
      text: chart.yLabel,
      fontFamily: 'sans',
      fontSize: 11,
      textAlign: 'right',
      strokeColor: '#475569',
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash('xy-y-label'),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
  }

  const ySpan = chart.yMax - chart.yMin || 1
  const yToPx = (v: number): number =>
    plotY1 - ((v - chart.yMin) / ySpan) * PLOT_HEIGHT

  // Y axis tick labels — 5 evenly spaced ticks (0%, 25%, 50%, 75%, 100%).
  for (let t = 0; t <= 4; t++) {
    const v = chart.yMin + (ySpan * t) / 4
    const yPx = yToPx(v)
    out.push({
      type: 'text',
      x: ox,
      y: yPx - 7,
      width: Y_AXIS_LABEL_WIDTH - 8,
      height: 14,
      text: formatTick(v),
      fontFamily: 'mono',
      fontSize: 10,
      textAlign: 'right',
      strokeColor: '#475569',
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash(`xy-y-tick-${t}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
  }

  // X axis tick labels — one per declared label, centred under each
  // category band.
  const n = Math.max(1, chart.xLabels.length)
  const slotWidth = PLOT_WIDTH / n
  chart.xLabels.forEach((label, idx) => {
    const cx = plotX0 + (idx + 0.5) * slotWidth
    out.push({
      type: 'text',
      x: cx - slotWidth / 2,
      y: plotY1 + 4,
      width: slotWidth,
      height: X_AXIS_LABEL_HEIGHT - 6,
      text: label,
      fontFamily: 'sans',
      fontSize: 11,
      textAlign: 'center',
      strokeColor: '#475569',
      fillColor: 'transparent',
      fillStyle: 'none',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 100,
      seed: hash(`xy-x-tick-${idx}`),
      version: 0,
      locked: false,
      angle: 0,
      zIndex: 0,
      groupIds: [],
    } as CreateElementInput)
  })

  // Series — one rect per bar value (bar) or one line segment per
  // adjacent pair (line).
  chart.series.forEach((series, sIdx) => {
    const colour = SERIES_PALETTE[sIdx % SERIES_PALETTE.length]
    if (series.kind === 'bar') {
      const barWidth = slotWidth * (1 - BAR_GAP_FRACTION)
      series.values.forEach((v, idx) => {
        const cx = plotX0 + (idx + 0.5) * slotWidth
        const top = yToPx(v)
        const baseline = yToPx(Math.max(chart.yMin, 0))
        const y = Math.min(top, baseline)
        const h = Math.abs(baseline - top)
        if (h < 1) return
        out.push({
          type: 'rect',
          x: cx - barWidth / 2,
          y,
          width: barWidth,
          height: h,
          strokeColor: colour,
          fillColor: colour,
          fillStyle: 'solid',
          strokeWidth: 1,
          strokeStyle: 'solid',
          roughness: 0,
          opacity: 80,
          seed: hash(`xy-bar-${sIdx}-${idx}`),
          version: 0,
          locked: false,
          angle: 0,
          zIndex: 0,
          groupIds: [],
          roundness: 2,
        } as CreateElementInput)
      })
      return
    }
    // line series — emit a line segment per adjacent pair.
    for (let i = 1; i < series.values.length; i++) {
      const x0 = plotX0 + (i - 0.5) * slotWidth
      const x1 = plotX0 + (i + 0.5) * slotWidth
      const y0 = yToPx(series.values[i - 1])
      const y1 = yToPx(series.values[i])
      const minX = Math.min(x0, x1)
      const minY = Math.min(y0, y1)
      out.push({
        type: 'line',
        x: minX,
        y: minY,
        width: Math.abs(x1 - x0),
        height: Math.abs(y1 - y0),
        points: [x0 - minX, y0 - minY, x1 - minX, y1 - minY],
        strokeColor: colour,
        fillColor: 'transparent',
        fillStyle: 'none',
        strokeWidth: 2,
        strokeStyle: 'solid',
        roughness: 0,
        opacity: 100,
        seed: hash(`xy-line-${sIdx}-${i}`),
        version: 0,
        locked: false,
        angle: 0,
        zIndex: 0,
        groupIds: [],
      } as CreateElementInput)
    }
  })

  return out
}

/** Compact tick formatter — drops trailing decimals when integer-
 *  valued, keeps two places otherwise. */
function formatTick(v: number): string {
  if (Number.isInteger(v)) return String(v)
  return v.toFixed(2).replace(/0+$/, '').replace(/\.$/, '')
}

function hash(s: string): number {
  let h = 5381
  for (let i = 0; i < s.length; i++) h = (h * 33) ^ s.charCodeAt(i)
  return h >>> 0
}
