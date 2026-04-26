/**
 * GenericChart - Rapidly analytics visualization component.
 *
 * Renders line, area, or bar charts with configurable series, tooltips,
 * legends, and theme-aware gradients. Wraps recharts primitives via
 * the @rapidly-tech/ui chart components.
 */

import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
} from '@rapidly-tech/ui/components/primitives/chart'
import { useCallback, useId, useMemo, useState } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  XAxis,
  YAxis,
} from 'recharts'
import type { ExternalMouseEvents } from 'recharts/types/chart/types'
import type { AxisTick } from 'recharts/types/util/types'

// ── Helpers ──

/** Ensures bars with zero-height values still render with a visible minimum. */
function FloorBar(props: {
  x?: number
  y?: number
  width?: number
  height?: number
  fill?: string
  radius?: number
  opacity?: number
}) {
  const VISIBLE_MINIMUM = 4
  const {
    fill,
    radius = 1,
    opacity = 1,
    width = 0,
    x = 0,
    y = 0,
    height = 0,
  } = props
  const clampedHeight = height === 0 ? VISIBLE_MINIMUM : height
  const adjustedY = height === 0 ? y - VISIBLE_MINIMUM : y

  return (
    <rect
      rx={radius}
      ry={radius}
      x={x}
      y={adjustedY}
      width={width}
      height={clampedHeight}
      fill={fill}
      opacity={opacity}
    />
  )
}

/** Humanize a snake_case series key into a display label. */
const humanizeKey = (raw: string): string => raw.toString().split('_').join(' ')

/** Build a chart config record from series definitions. */
function buildSeriesConfig(
  seriesList: GenericChartSeries[],
): Record<string, { label: string; color: string }> {
  const cfg: Record<string, { label: string; color: string }> = {}
  for (const entry of seriesList) {
    cfg[entry.key] = { label: entry.label, color: entry.color }
  }
  return cfg
}

/** Determine the area gradient type from primary series data. */
type GradientKind = 'positive' | 'negative' | 'mixed'
interface GradientMeta {
  kind: GradientKind
  zeroRatio: number
}

function analyzeGradient<T extends Record<string, unknown>>(
  rows: T[],
  seriesKey: string | undefined,
): GradientMeta {
  if (!seriesKey) return { kind: 'positive', zeroRatio: 1 }

  const nums = rows.map((r) => (r[seriesKey] as number) || 0)
  const ceiling = Math.max(...nums)
  const floor = Math.min(...nums)

  if (ceiling <= 0) return { kind: 'negative', zeroRatio: 0 }
  if (floor >= 0) return { kind: 'positive', zeroRatio: 1 }

  return {
    kind: 'mixed',
    zeroRatio: ceiling / (ceiling - floor),
  }
}

// ── Public Types ──

export interface GenericChartSeries {
  key: string
  label: string
  color: string
}

export interface GenericChartProps<T extends Record<string, unknown>> {
  ref?: React.RefObject<HTMLDivElement | null>
  data: T[]
  series: GenericChartSeries[]
  xAxisKey: keyof T

  // Recharts passes untyped axis values at runtime; bivariant callback for compatibility
  xAxisFormatter?: {
    bivarianceHack(value: string | number | Date): string
  }['bivarianceHack']
  valueFormatter?: (value: number, seriesKey: string) => React.ReactNode
  height?: number
  width?: number
  showGrid?: boolean
  showYAxis?: boolean
  showLegend?: boolean
  chartType?: 'line' | 'bar'
  onDataIndexHover?: (index: number | null) => void
  simple?: boolean
  ticks?: AxisTick[]
}

// ── Component ──

export const GenericChart = <T extends Record<string, unknown>>({
  ref,
  data,
  series,
  xAxisKey,
  xAxisFormatter,
  valueFormatter,
  height,
  width,
  showGrid = false,
  showYAxis = false,
  showLegend = false,
  chartType = 'line',
  onDataIndexHover,
  simple = false,
  ticks: ticksProp,
}: GenericChartProps<T>) => {
  const [highlightedKey, setHighlightedKey] = useState<string | null>(null)
  const instanceId = useId()

  // Toggle a series for legend highlight
  const toggleHighlight = useCallback((seriesKey: string) => {
    setHighlightedKey((prev) => (prev === seriesKey ? null : seriesKey))
  }, [])

  // Derive chart configuration from series definitions
  const chartConfig = useMemo(() => buildSeriesConfig(series), [series])

  // Resolve tick marks for the x-axis
  const resolvedTicks = useMemo((): AxisTick[] | undefined => {
    if (ticksProp) return ticksProp
    if (!simple || data.length === 0) return undefined
    const first = data[0]?.[xAxisKey] as AxisTick
    const last = data[data.length - 1]?.[xAxisKey] as AxisTick
    return [first, last].filter((tick): tick is AxisTick => tick !== undefined)
  }, [ticksProp, simple, data, xAxisKey])

  // Check whether the dataset contains fractional numbers
  const hasFractions = useMemo(
    () =>
      data.some((row) =>
        series.some((s) => {
          const val = row[s.key]
          return typeof val === 'number' && val % 1 !== 0
        }),
      ),
    [data, series],
  )

  // ── Tooltip Renderer ──

  const renderTooltipRow = useCallback(
    (
      value: number | undefined,
      name: string | undefined,
      entry?: { color?: string },
    ) => {
      if (value == null || !name) return null

      const display = valueFormatter ? valueFormatter(value, name) : value
      return (
        <div className="flex w-40 flex-row justify-between gap-x-8">
          <div className="flex flex-row items-center gap-x-2">
            <span
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: entry?.color }}
            />
            <span className="capitalize">{humanizeKey(name)}</span>
          </div>
          <span>{display}</span>
        </div>
      )
    },
    [valueFormatter],
  )

  // ── Gradient Analysis ──

  const leadSeries = series[0]
  const gradient = useMemo(
    () => analyzeGradient(data, leadSeries?.key),
    [data, leadSeries],
  )

  // ── Build Chart Content ──

  const chartBody = useMemo(() => {
    // Shared layout properties
    const baseProps = {
      accessibilityLayer: true,
      data,
      margin: {
        left: showYAxis ? 4 : 24,
        right: 24,
        top: 24,
        bottom: showLegend ? 12 : undefined,
      },
      onMouseMove: ((state) => {
        if (!onDataIndexHover) return
        const raw = state.activeTooltipIndex
        const idx =
          typeof raw === 'number'
            ? raw
            : typeof raw === 'string'
              ? parseInt(raw, 10)
              : null
        onDataIndexHover(Number.isNaN(idx) ? null : idx)
      }) satisfies ExternalMouseEvents['onMouseMove'],
      onMouseLeave: (() => {
        onDataIndexHover?.(null)
      }) satisfies ExternalMouseEvents['onMouseLeave'],
    }

    // Vertical grid lines
    const gridElement =
      showGrid || !simple ? (
        <CartesianGrid
          vertical={true}
          horizontal={false}
          stroke="var(--chart-grid)"
          strokeDasharray="6 6"
          syncWithTicks={true}
        />
      ) : undefined

    // Horizontal axis
    const xAxisElement = (
      <XAxis
        dataKey={xAxisKey as string}
        axisLine={false}
        tickLine={false}
        tickMargin={8}
        interval="equidistantPreserveStart"
        ticks={resolvedTicks}
        tickFormatter={xAxisFormatter ? (v) => xAxisFormatter(v) : undefined}
      />
    )

    // Vertical axis (optional)
    const yAxisElement = showYAxis ? (
      <YAxis
        axisLine={false}
        tickLine={false}
        allowDecimals={hasFractions}
        tickMargin={4}
        width="auto"
      />
    ) : undefined

    // Tooltip overlay
    const tooltipElement = (
      <ChartTooltip
        cursor={true}
        content={(p) => (
          <ChartTooltipContent
            active={p.active}
            payload={
              p.payload as React.ComponentProps<
                typeof ChartTooltipContent
              >['payload']
            }
            label={p.label}
            coordinate={p.coordinate}
            accessibilityLayer={p.accessibilityLayer}
            activeIndex={p.activeIndex}
            className="rp-text-primary"
            indicator="dot"
            labelKey={leadSeries?.key}
            formatter={renderTooltipRow}
          />
        )}
      />
    )

    // Legend (interactive when multiple series)
    const legendElement = showLegend ? (
      <ChartLegend
        content={
          <ChartLegendContent>
            <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 pt-3">
              {series.map((s) => {
                const isActive =
                  highlightedKey === null || highlightedKey === s.key
                const canClick = series.length > 1
                return (
                  <div
                    key={s.key}
                    className={`flex items-center gap-1.5 whitespace-nowrap transition-opacity ${canClick ? 'cursor-pointer' : ''}`}
                    style={{ opacity: isActive ? 1 : 0.3 }}
                    onClick={
                      canClick ? () => toggleHighlight(s.key) : undefined
                    }
                  >
                    <div
                      className="h-2 w-2 shrink-0 rounded-[2px]"
                      style={{ backgroundColor: s.color }}
                    />
                    {s.label}
                  </div>
                )
              })}
            </div>
          </ChartLegendContent>
        }
      />
    ) : undefined

    // Determine series visibility
    const isSeriesVisible = (key: string) =>
      highlightedKey === null || highlightedKey === key

    // ── Bar chart variant ──
    if (chartType === 'bar') {
      return (
        <BarChart {...baseProps}>
          {gridElement}
          {xAxisElement}
          {yAxisElement}
          {tooltipElement}
          {legendElement}
          {[...series].reverse().map((s) => (
            <Bar
              key={s.key}
              dataKey={s.key}
              fill={`var(--color-${s.key})`}
              radius={4}
              maxBarSize={32}
              opacity={isSeriesVisible(s.key) ? 1 : 0.3}
              shape={<FloorBar />}
            />
          ))}
        </BarChart>
      )
    }

    // ── Multi-series line chart ──
    if (series.length > 1) {
      return (
        <LineChart {...baseProps}>
          {gridElement}
          {xAxisElement}
          {yAxisElement}
          {tooltipElement}
          {legendElement}
          {series.map((s) => (
            <Line
              key={s.key}
              dataKey={s.key}
              stroke={`var(--color-${s.key})`}
              type="linear"
              dot={false}
              strokeWidth={1.5}
              strokeOpacity={isSeriesVisible(s.key) ? 1 : 0.3}
            />
          ))}
        </LineChart>
      )
    }

    // ── Single-series area chart ──
    if (!leadSeries) return null

    const seriesColor = `var(--color-${leadSeries.key})`
    const gradientId = `rapidly-area-fill-${instanceId}`

    const renderGradientStops = () => {
      switch (gradient.kind) {
        case 'positive':
          return (
            <>
              <stop offset="0%" stopColor={seriesColor} stopOpacity={0.5} />
              <stop offset="100%" stopColor={seriesColor} stopOpacity={0.025} />
            </>
          )
        case 'negative':
          return (
            <>
              <stop offset="0%" stopColor={seriesColor} stopOpacity={0.025} />
              <stop offset="100%" stopColor={seriesColor} stopOpacity={0.5} />
            </>
          )
        case 'mixed':
          return (
            <>
              <stop offset="0%" stopColor={seriesColor} stopOpacity={0.5} />
              <stop
                offset={`${gradient.zeroRatio * 100}%`}
                stopColor={seriesColor}
                stopOpacity={0.025}
              />
              <stop offset="100%" stopColor={seriesColor} stopOpacity={0.5} />
            </>
          )
      }
    }

    return (
      <AreaChart {...baseProps}>
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            {renderGradientStops()}
          </linearGradient>
        </defs>
        {gridElement}
        {xAxisElement}
        {yAxisElement}
        {tooltipElement}
        {legendElement}
        <Area
          dataKey={leadSeries.key}
          stroke={seriesColor}
          fill={`url(#${gradientId})`}
          type="linear"
          strokeWidth={1.5}
        />
      </AreaChart>
    )
  }, [
    data,
    chartType,
    series,
    leadSeries,
    showGrid,
    simple,
    resolvedTicks,
    xAxisKey,
    xAxisFormatter,
    showYAxis,
    hasFractions,
    renderTooltipRow,
    showLegend,
    highlightedKey,
    toggleHighlight,
    onDataIndexHover,
    gradient,
    instanceId,
  ])

  return (
    <ChartContainer
      ref={ref}
      style={{ height, width: width || '100%' }}
      config={chartConfig}
    >
      {chartBody}
    </ChartContainer>
  )
}

GenericChart.displayName = 'GenericChart'

export default GenericChart
