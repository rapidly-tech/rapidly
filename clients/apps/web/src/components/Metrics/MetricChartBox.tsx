'use client'

/**
 * MetricChartBox - primary analytics card for the Rapidly dashboard.
 *
 * Displays a metric name/value header, optional comparison trend badge,
 * interactive chart, and share-as-image modal. Supports compact and
 * full-size layouts.
 */

import Spinner from '@/components/Shared/Spinner'
import { ParsedMetricsResponse } from '@/hooks/api'
import { getFormattedMetricValue } from '@/utils/metrics'
import { Icon } from '@iconify/react'
import { schemas } from '@rapidly-tech/client'
import FormattedDateTime from '@rapidly-tech/ui/components/data/FormattedDateTime'
import FormattedInterval from '@rapidly-tech/ui/components/data/FormattedInterval'
import { Status } from '@rapidly-tech/ui/components/feedback/Status'
import Button from '@rapidly-tech/ui/components/forms/Button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@rapidly-tech/ui/components/forms/Select'
import ElevatedCard from '@rapidly-tech/ui/components/layout/ElevatedCard'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@rapidly-tech/ui/components/primitives/tooltip'
import React, { useCallback, useMemo, useState } from 'react'
import { twMerge } from 'tailwind-merge'
import { Modal } from '../Modal'
import { useModal } from '../Modal/useModal'
import MetricChart from './MetricChart'
import { ShareChartModal } from './ShareChartModal'

// ── Types ──

interface MetricOption {
  slug: keyof schemas['Metrics']
  display_name: string
}

interface MetricChartBoxProps {
  metric: keyof schemas['Metrics']
  onMetricChange?: (metric: keyof schemas['Metrics']) => void
  data?: ParsedMetricsResponse
  previousData?: ParsedMetricsResponse
  interval: schemas['TimeInterval']
  className?: string
  height?: number
  width?: number
  loading?: boolean
  compact?: boolean
  shareable?: boolean
  simple?: boolean
  chartType?: 'line' | 'bar'
  /** Override the list of metrics shown in the dropdown. If not provided, uses metrics from data. */
  availableMetrics?: MetricOption[]
}

// ── Constants ──

const EXPERIMENTAL_METRICS: Record<string, { tooltip: string }> = {}

// ── Helpers ──

/** Extract the first and last timestamps from a periods array. */
function extractDateBounds(
  periods: { timestamp: Date }[] | undefined,
): [Date | null, Date | null] {
  if (!periods || periods.length === 0) return [null, null]
  return [periods[0].timestamp, periods[periods.length - 1].timestamp]
}

/** Compute percentage change between two values. */
function percentChange(current: number, previous: number): number {
  if (previous === 0) return 0
  return ((current - previous) / previous) * 100
}

/** Format trend as signed percentage string. */
function formatTrend(pct: number): string {
  return pct > 0 ? `+${pct.toFixed(0)}%` : `${pct.toFixed(0)}%`
}

// ── Component ──

const MetricChartBox = ({
  ref,
  metric,
  onMetricChange,
  data,
  previousData,
  interval,
  className,
  height = 300,
  width,
  loading,
  compact = false,
  shareable = true,
  simple = false,
  chartType = 'line',
  availableMetrics,
}: MetricChartBoxProps & {
  ref?: React.RefObject<HTMLDivElement>
}) => {
  const { isShown: isModalOpen, show: openModal, hide: closeModal } = useModal()
  const [focusedIdx, setFocusedIdx] = useState<number | null>(null)

  // ── Date Boundaries ──
  const [rangeStart, rangeEnd] = useMemo(
    () => extractDateBounds(data?.periods),
    [data],
  )
  const [prevRangeStart, prevRangeEnd] = useMemo(
    () => extractDateBounds(previousData?.periods),
    [previousData],
  )

  // ── Active Metric Definition ──
  const activeMetric = useMemo(() => data?.metrics[metric], [data, metric])

  // ── Hovered Period Lookups ──
  const focusedPeriod = useMemo(() => {
    if (!data || focusedIdx == null) return null
    return data.periods[focusedIdx]
  }, [data, focusedIdx])

  const focusedPrevPeriod = useMemo(() => {
    if (!previousData || focusedIdx == null) return null
    return previousData.periods[focusedIdx]
  }, [previousData, focusedIdx])

  // ── Displayed Value ──
  const displayValue = useMemo(() => {
    if (!data) return 0
    const info = data.metrics[metric]
    if (!info) return 0

    if (focusedPeriod) {
      return getFormattedMetricValue(info, focusedPeriod[metric] ?? 0)
    }
    return getFormattedMetricValue(info, data.totals[metric] ?? 0)
  }, [focusedPeriod, data, metric])

  // ── Trend Calculation ──
  const trendPct = useMemo(() => {
    if (!data || !previousData) return 0

    const currentRow = focusedPeriod ?? data.periods[data.periods.length - 1]
    const previousRow =
      focusedPrevPeriod ?? previousData.periods[previousData.periods.length - 1]

    if (!currentRow || !previousRow) return 0
    return percentChange(currentRow[metric] ?? 0, previousRow[metric] ?? 0)
  }, [data, previousData, focusedPeriod, focusedPrevPeriod, metric])

  // ── Handlers ──
  const handleHover = useCallback(
    (idx: number | null) => setFocusedIdx(idx),
    [],
  )

  // ── Experimental badge helper ──
  const experimentalBadge = (metricKey: string) => {
    if (!(metricKey in EXPERIMENTAL_METRICS)) return null
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="inline-flex cursor-help">
            <Status
              status="Experimental"
              className="bg-slate-200 text-xs text-slate-600 dark:bg-slate-900 dark:text-slate-400"
            />
          </span>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs">
          {EXPERIMENTAL_METRICS[metricKey]?.tooltip}
        </TooltipContent>
      </Tooltip>
    )
  }

  // ── Dropdown or static header ──
  const metricHeader = onMetricChange ? (
    <div className="flex flex-row items-center gap-x-2">
      <Select value={metric} onValueChange={onMetricChange}>
        <SelectTrigger className="-mt-2 -ml-3 h-fit w-fit rounded-lg border-0 border-none bg-transparent px-3 py-2 shadow-none ring-0 transition-colors hover:bg-slate-200 focus-visible:ring-0 focus-visible:ring-offset-0 dark:hover:bg-slate-800">
          <SelectValue placeholder="Select a metric" />
        </SelectTrigger>
        <SelectContent className="ring-1 ring-slate-200 dark:bg-slate-900 dark:ring-slate-800">
          {availableMetrics
            ? availableMetrics.map((m) => (
                <SelectItem key={m.slug} value={m.slug}>
                  {m.display_name}
                </SelectItem>
              ))
            : data &&
              Object.values(data.metrics)
                .filter(
                  (m): m is NonNullable<typeof m> =>
                    m !== null && m !== undefined,
                )
                .map((m) => (
                  <SelectItem key={m.slug} value={m.slug}>
                    {m.display_name}
                  </SelectItem>
                ))}
        </SelectContent>
      </Select>
      {experimentalBadge(metric)}
    </div>
  ) : (
    <div className="flex flex-row items-center gap-x-2">
      <h3 className={compact ? 'text-base' : 'text-lg'}>
        {activeMetric?.display_name}
      </h3>
      {experimentalBadge(metric)}
    </div>
  )

  // ── Trend badge ──
  const showTrend = trendPct !== 0 && !isNaN(trendPct) && trendPct !== Infinity
  const trendBadge = showTrend ? (
    <Status
      status={formatTrend(trendPct)}
      className={twMerge(
        'text-sm',
        trendPct > 0
          ? 'bg-emerald-100 text-emerald-500 dark:bg-emerald-950'
          : 'bg-red-100 text-red-500 dark:bg-red-950',
      )}
    />
  ) : null

  // ── Render ──
  return (
    <ElevatedCard
      ref={ref}
      className={twMerge(
        'group flex w-full flex-col justify-between bg-slate-50 p-2 shadow-xs dark:bg-slate-900',
        className,
      )}
    >
      {/* Header section */}
      <div
        className={twMerge(
          'flex flex-col gap-6 md:flex-row md:items-start md:justify-between',
          compact ? 'p-4' : 'p-6',
        )}
      >
        <div
          className={twMerge(
            'flex w-full',
            compact
              ? 'flex-row items-center justify-between gap-x-4'
              : 'flex-col gap-y-4',
          )}
        >
          {metricHeader}
          <h2 className={compact ? 'text-base' : 'text-5xl font-light'}>
            {displayValue}
          </h2>
          {!compact && (
            <div className="flex flex-col gap-x-6 gap-y-2 md:flex-row md:items-center">
              {/* Current period indicator */}
              <div className="flex flex-row items-center gap-x-2 text-sm">
                <span className="h-3 w-3 rounded-full border-2 border-slate-500" />
                {focusedPeriod ? (
                  <FormattedDateTime
                    datetime={focusedPeriod.timestamp}
                    dateStyle="medium"
                  />
                ) : (
                  <span className="text-slate-500 dark:text-slate-400">
                    {rangeStart && rangeEnd && (
                      <FormattedInterval
                        startDatetime={rangeStart}
                        endDatetime={rangeEnd}
                        hideCurrentYear={false}
                      />
                    )}
                  </span>
                )}
              </div>
              {/* Previous period indicator */}
              {previousData && (
                <div className="flex flex-row items-center gap-x-2 text-sm">
                  <span className="h-3 w-3 rounded-full border-2 border-slate-500 dark:border-slate-700" />
                  {focusedPrevPeriod ? (
                    <FormattedDateTime
                      datetime={focusedPrevPeriod.timestamp}
                      dateStyle="medium"
                    />
                  ) : (
                    <span className="text-slate-500 dark:text-slate-400">
                      {prevRangeStart && prevRangeEnd && (
                        <FormattedInterval
                          startDatetime={prevRangeStart}
                          endDatetime={prevRangeEnd}
                          hideCurrentYear={false}
                        />
                      )}
                    </span>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right-side actions: trend badge + share button */}
        <div className="flex flex-row items-center gap-x-4">
          {trendBadge}
          {shareable && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="hidden rounded-full opacity-0 transition-opacity group-hover:opacity-100 md:block"
                  onClick={openModal}
                >
                  <Icon
                    icon="solar:arrow-right-up-linear"
                    className="h-4 w-4"
                  />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Share Chart</TooltipContent>
            </Tooltip>
          )}
        </div>
      </div>

      {/* Chart area */}
      <div
        className={twMerge(
          'flex w-full flex-col gap-y-2 rounded-3xl bg-white dark:bg-slate-950',
          compact ? 'p-2' : 'p-4',
        )}
      >
        {loading ? (
          <div
            style={{ height }}
            className="flex flex-col items-center justify-center"
          >
            <Spinner />
          </div>
        ) : data && activeMetric ? (
          <MetricChart
            height={height}
            width={width}
            data={data.periods}
            previousData={previousData?.periods}
            interval={interval}
            metric={activeMetric}
            onDataIndexHover={handleHover}
            simple={simple}
            chartType={chartType}
          />
        ) : (
          <div
            className="flex w-full flex-col items-center justify-center"
            style={{ height }}
          >
            <span className="text-lg">No data available</span>
          </div>
        )}
      </div>

      {/* Share modal */}
      {shareable && data && (
        <Modal
          title={`Share ${activeMetric?.display_name} Metric`}
          className="lg:w-fit!"
          isShown={isModalOpen}
          hide={closeModal}
          modalContent={
            <ShareChartModal
              data={data}
              previousData={previousData}
              interval={interval}
              metric={activeMetric?.slug as keyof schemas['Metrics']}
            />
          }
        />
      )}
    </ElevatedCard>
  )
}

MetricChartBox.displayName = 'MetricChartBox'

export default MetricChartBox
