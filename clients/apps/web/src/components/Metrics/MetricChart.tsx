/**
 * MetricChart - renders a time-series metric with optional
 * prior-period overlay for comparison in the Rapidly dashboard.
 */

import { ParsedMetricPeriod } from '@/hooks/api'
import { getFormattedMetricValue, getTimestampFormatter } from '@/utils/metrics'
import { schemas } from '@rapidly-tech/client'
import { useMemo } from 'react'
import type { AxisTick } from 'recharts/types/util/types'
import { GenericChart } from '../Charts/GenericChart'

// ── Helpers ──

/** Map raw metric periods into the generic { timestamp, current, previous? } shape. */
function buildChartData(
  periods: ParsedMetricPeriod[],
  metricSlug: string,
  comparison?: ParsedMetricPeriod[],
) {
  return periods.map((period, idx) => {
    const entry: { timestamp: unknown; [key: string]: unknown } = {
      timestamp: period.timestamp,
      current:
        period[metricSlug as keyof Omit<ParsedMetricPeriod, 'timestamp'>],
    }
    const prev = comparison?.[idx]
    if (prev) {
      entry.previous =
        prev[metricSlug as keyof Omit<ParsedMetricPeriod, 'timestamp'>]
    }
    return entry
  })
}

/** Produce endpoint-only tick marks for simplified charts. */
function edgeTicks<T extends { timestamp: unknown }>(
  rows: T[],
): AxisTick[] | undefined {
  if (rows.length === 0) return undefined
  return [
    rows[0]?.timestamp as AxisTick,
    rows[rows.length - 1]?.timestamp as AxisTick,
  ].filter((t): t is AxisTick => t !== undefined)
}

// ── Props ──

interface MetricChartProps {
  ref?: React.RefObject<HTMLDivElement | null>
  data: ParsedMetricPeriod[]
  previousData?: ParsedMetricPeriod[]
  interval: schemas['TimeInterval']
  metric: schemas['Metric']
  height?: number
  width?: number
  grid?: boolean
  onDataIndexHover?: (index: number | null) => void
  simple?: boolean
  showYAxis?: boolean
  chartType?: 'line' | 'bar'
}

// ── Component ──

const MetricChart = ({
  ref,
  data,
  previousData,
  interval,
  metric,
  height,
  width,
  grid,
  onDataIndexHover,
  simple = false,
  showYAxis = false,
  chartType = 'line',
}: MetricChartProps) => {
  const chartData = useMemo(
    () => buildChartData(data, metric.slug, previousData),
    [data, previousData, metric.slug],
  )

  const seriesDefinitions = useMemo(() => {
    const items = []
    if (previousData) {
      items.push({
        key: 'previous',
        label: 'Previous Period',
        color: 'var(--chart-line-previous)',
      })
    }
    items.push({
      key: 'current',
      label: 'Current Period',
      color: 'var(--chart-line)',
    })
    return items
  }, [previousData])

  const formatTimestamp = useMemo(
    () => getTimestampFormatter(interval),
    [interval],
  )

  const formatValue = useMemo(
    () => (val: number) => getFormattedMetricValue(metric, val),
    [metric],
  )

  const tickMarks = useMemo(
    () => (simple ? edgeTicks(chartData) : undefined),
    [simple, chartData],
  )

  return (
    <GenericChart
      ref={ref}
      data={chartData}
      series={seriesDefinitions}
      xAxisKey="timestamp"
      xAxisFormatter={formatTimestamp}
      valueFormatter={formatValue}
      height={height}
      width={width}
      showGrid={grid}
      showYAxis={showYAxis}
      chartType={chartType}
      onDataIndexHover={onDataIndexHover}
      simple={simple}
      ticks={tickMarks}
    />
  )
}

MetricChart.displayName = 'MetricChart'

export default MetricChart
