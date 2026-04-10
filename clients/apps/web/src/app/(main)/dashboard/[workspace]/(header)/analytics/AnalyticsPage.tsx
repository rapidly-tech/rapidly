'use client'

import { DashboardBody } from '@/components/Layout/DashboardLayout'
import DateRangePicker from '@/components/Metrics/DateRangePicker'
import IntervalPicker, {
  getNextValidInterval,
} from '@/components/Metrics/IntervalPicker'
import MetricChartBox from '@/components/Metrics/MetricChartBox'
import { useMetrics } from '@/hooks/api'
import { fromISODate, toISODate } from '@/utils/metrics'
import { schemas } from '@rapidly-tech/client'
import { subMonths } from 'date-fns/subMonths'
import { createParser, parseAsStringLiteral, useQueryState } from 'nuqs'
import { useCallback, useMemo, useState } from 'react'
import { twMerge } from 'tailwind-merge'

// ── Constants ──

const TIME_INTERVALS = ['hour', 'day', 'week', 'month', 'year'] as const

// ── Parsers ──

const parseAsISODate = createParser({
  parse: (value) => {
    if (!value) return null
    const date = fromISODate(value)
    return isNaN(date.getTime()) ? null : date
  },
  serialize: (date) => toISODate(date),
})

// ── Metric Definitions ──

const ACTIVITY_METRICS: {
  slug: keyof schemas['Metrics']
  display_name: string
}[] = [
  {
    slug: 'file_share_sessions' as keyof schemas['Metrics'],
    display_name: 'File Shares',
  },
  {
    slug: 'file_share_downloads' as keyof schemas['Metrics'],
    display_name: 'Downloads',
  },
  {
    slug: 'file_share_free_sessions' as keyof schemas['Metrics'],
    display_name: 'Free File Shares',
  },
  {
    slug: 'file_share_active_sessions' as keyof schemas['Metrics'],
    display_name: 'Active Sessions',
  },
  {
    slug: 'file_share_completed_sessions' as keyof schemas['Metrics'],
    display_name: 'Completed Sessions',
  },
  {
    slug: 'file_share_expired_sessions' as keyof schemas['Metrics'],
    display_name: 'Expired Sessions',
  },
  {
    slug: 'file_share_avg_downloads' as keyof schemas['Metrics'],
    display_name: 'Avg Downloads Per Share',
  },
  {
    slug: 'cumulative_file_share_sessions' as keyof schemas['Metrics'],
    display_name: 'Cumulative File Shares',
  },
  {
    slug: 'cumulative_file_share_downloads' as keyof schemas['Metrics'],
    display_name: 'Cumulative Downloads',
  },
]

const ACTIVITY_METRIC_SLUGS = ACTIVITY_METRICS.map((m) => m.slug) as string[]

// ── Main Component ──

export default function AnalyticsPage({
  workspace,
}: {
  workspace: schemas['Workspace']
}) {
  const defaultStartDate = useMemo(() => subMonths(new Date(), 1), [])
  const defaultEndDate = useMemo(() => new Date(), [])

  const [interval, setInterval] = useQueryState(
    'interval',
    parseAsStringLiteral(TIME_INTERVALS).withDefault('day'),
  )

  const [startDate, setStartDate] = useQueryState(
    'start_date',
    parseAsISODate.withDefault(defaultStartDate),
  )

  const [endDate, setEndDate] = useQueryState(
    'end_date',
    parseAsISODate.withDefault(defaultEndDate),
  )

  const dateRange = useMemo(
    () => ({ from: startDate, to: endDate }),
    [startDate, endDate],
  )

  // ── Date & Interval Handlers ──

  const onIntervalChange = useCallback(
    (newInterval: schemas['TimeInterval']) => {
      setInterval(newInterval)
    },
    [setInterval],
  )

  const onDateChange = useCallback(
    (dateRange: { from: Date; to: Date }) => {
      const validInterval = getNextValidInterval(
        interval,
        dateRange.from,
        dateRange.to,
      )
      setStartDate(dateRange.from)
      setEndDate(dateRange.to)
      setInterval(validInterval)
    },
    [interval, setStartDate, setEndDate, setInterval],
  )

  // ── Data Query ──

  const [heroMetric, setHeroMetric] = useState<keyof schemas['Metrics']>(
    'file_share_sessions' as keyof schemas['Metrics'],
  )

  const {
    data: metricsData,
    isLoading: metricsLoading,
    isError: metricsError,
  } = useMetrics({
    startDate,
    endDate,
    interval,
    workspace_id: workspace.id,
    metrics: ACTIVITY_METRIC_SLUGS,
  })

  const GRID_METRICS = ACTIVITY_METRICS.filter(
    (m) =>
      m.slug !== heroMetric &&
      m.slug !==
        ('cumulative_file_share_sessions' as keyof schemas['Metrics']) &&
      m.slug !==
        ('cumulative_file_share_downloads' as keyof schemas['Metrics']),
  )

  return (
    <DashboardBody className="gap-y-8 pb-16 md:gap-y-12">
      <div className="flex flex-col gap-y-8">
        {/* Date/Interval Controls */}
        <div className="flex flex-col items-center gap-2 lg:flex-row">
          <div className="w-full lg:w-auto">
            <IntervalPicker
              interval={interval}
              onChange={onIntervalChange}
              startDate={startDate}
              endDate={endDate}
            />
          </div>
          <div className="w-full lg:w-auto">
            <DateRangePicker
              date={dateRange}
              onDateChange={onDateChange}
              className="w-full"
            />
          </div>
        </div>

        {metricsError ? (
          <div className="rounded-lg bg-red-50 p-4 text-sm text-red-600 dark:bg-red-900/20 dark:text-red-400">
            Failed to load analytics data. Please try again later.
          </div>
        ) : metricsLoading ? (
          <div className="flex flex-col gap-y-6">
            <div className="h-[340px] animate-pulse rounded-2xl bg-slate-100 dark:bg-slate-800" />
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {[...Array(6)].map((_, i) => (
                <div
                  key={i}
                  className="h-[240px] animate-pulse rounded-2xl bg-slate-100 dark:bg-slate-800"
                />
              ))}
            </div>
          </div>
        ) : (
          <>
            {/* Hero Chart - switchable metric */}
            <MetricChartBox
              data={metricsData}
              interval={interval}
              metric={heroMetric}
              onMetricChange={(m) => setHeroMetric(m)}
              availableMetrics={ACTIVITY_METRICS}
              height={300}
              chartType="line"
            />

            {/* Grid of smaller charts */}
            <div className="glass-elevated flex flex-col overflow-hidden rounded-2xl bg-slate-50 shadow-xs lg:rounded-3xl dark:bg-slate-900">
              <div className="grid grid-cols-1 flex-col [clip-path:inset(1px_1px_1px_1px)] md:grid-cols-2 lg:grid-cols-3">
                {GRID_METRICS.map((m) => (
                  <MetricChartBox
                    key={m.slug}
                    data={metricsData}
                    interval={interval}
                    metric={m.slug}
                    height={200}
                    chartType="line"
                    compact
                    shareable={false}
                    className={twMerge(
                      'rounded-none! bg-transparent dark:bg-transparent',
                      'border-t-0 border-r border-b border-l-0 border-slate-200 shadow-none dark:border-slate-800',
                    )}
                  />
                ))}
              </div>
            </div>

            {/* Cumulative charts */}
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <MetricChartBox
                data={metricsData}
                interval={interval}
                metric={
                  'cumulative_file_share_sessions' as keyof schemas['Metrics']
                }
                height={200}
                chartType="line"
              />
              <MetricChartBox
                data={metricsData}
                interval={interval}
                metric={
                  'cumulative_file_share_downloads' as keyof schemas['Metrics']
                }
                height={200}
                chartType="line"
              />
            </div>
          </>
        )}
      </div>
    </DashboardBody>
  )
}
