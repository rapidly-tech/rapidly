'use client'

import DateRangePicker from '@/components/Metrics/DateRangePicker'
import IntervalPicker, {
  getNextValidInterval,
} from '@/components/Metrics/IntervalPicker'
import MetricChartBox from '@/components/Metrics/MetricChartBox'
import { SpinnerNoMargin as Spinner } from '@/components/Shared/Spinner'
import AccountBanner from '@/components/Transactions/AccountBanner'
import { useMetrics } from '@/hooks/api'
import { useStripeBalance } from '@/hooks/api/stripeConnect'
import { fromISODate, toISODate } from '@/utils/metrics'
import { schemas } from '@rapidly-tech/client'
import { formatCurrency } from '@rapidly-tech/currency'
import ElevatedCard from '@rapidly-tech/ui/components/layout/ElevatedCard'
import { subMonths } from 'date-fns/subMonths'
import { createParser, parseAsStringLiteral, useQueryState } from 'nuqs'
import { useCallback, useMemo } from 'react'
import { twMerge } from 'tailwind-merge'

const TIME_INTERVALS = ['hour', 'day', 'week', 'month', 'year'] as const

const parseAsISODate = createParser({
  parse: (value) => {
    if (!value) return null
    const date = fromISODate(value)
    return isNaN(date.getTime()) ? null : date
  },
  serialize: (date) => toISODate(date),
})

const FINANCE_METRICS: (keyof schemas['Metrics'])[] = [
  'file_share_revenue' as keyof schemas['Metrics'],
  'file_share_sessions' as keyof schemas['Metrics'],
  'file_share_downloads' as keyof schemas['Metrics'],
  'file_share_paid_sessions' as keyof schemas['Metrics'],
  'file_share_payment_conversion' as keyof schemas['Metrics'],
]

export default function ClientPage({
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

  const {
    data: balance,
    isLoading: balanceLoading,
    isError: balanceError,
  } = useStripeBalance(workspace.id)

  const {
    data: metricsData,
    isLoading: metricsLoading,
    isError: metricsError,
  } = useMetrics({
    startDate,
    endDate,
    interval,
    workspace_id: workspace.id,
    metrics: FINANCE_METRICS as string[],
  })

  return (
    <div className="flex flex-col gap-y-8">
      <AccountBanner workspace={workspace} />

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

      {/* Balance Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <ElevatedCard className="flex flex-col gap-2 p-6">
          <span className="text-sm text-slate-500 dark:text-slate-400">
            Available Balance
          </span>
          {balanceLoading ? (
            <Spinner className="h-6 w-6" />
          ) : balanceError ? (
            <span className="text-sm text-red-500 dark:text-red-400">
              Failed to load
            </span>
          ) : balance?.available && balance.available.length > 0 ? (
            <span className="text-2xl font-semibold">
              {formatCurrency(
                balance.available[0].amount,
                balance.available[0].currency,
              )}
            </span>
          ) : (
            <span className="text-slate-500 dark:text-slate-400">--</span>
          )}
        </ElevatedCard>
        <ElevatedCard className="flex flex-col gap-2 p-6">
          <span className="text-sm text-slate-500 dark:text-slate-400">
            Pending Balance
          </span>
          {balanceLoading ? (
            <Spinner className="h-6 w-6" />
          ) : balanceError ? (
            <span className="text-sm text-red-500 dark:text-red-400">
              Failed to load
            </span>
          ) : balance?.pending && balance.pending.length > 0 ? (
            <span className="text-2xl font-semibold">
              {formatCurrency(
                balance.pending[0].amount,
                balance.pending[0].currency,
              )}
            </span>
          ) : (
            <span className="text-slate-500 dark:text-slate-400">--</span>
          )}
        </ElevatedCard>
      </div>

      {/* Metric Charts */}
      {metricsError ? (
        <div className="rounded-lg bg-red-50 p-4 text-sm text-red-600 dark:bg-red-900/20 dark:text-red-400">
          Failed to load financial metrics. Please try again later.
        </div>
      ) : metricsLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[...Array(5)].map((_, i) => (
            <div
              key={i}
              className="h-[240px] animate-pulse rounded-2xl bg-slate-100 dark:bg-slate-800"
            />
          ))}
        </div>
      ) : metricsData ? (
        <div className="flex flex-col gap-y-6">
          <div className="glass-elevated flex flex-col overflow-hidden rounded-2xl bg-slate-50 shadow-xs lg:rounded-3xl dark:bg-slate-900">
            <div className="grid grid-cols-1 flex-col [clip-path:inset(1px_1px_1px_1px)] md:grid-cols-2 lg:grid-cols-3">
              {FINANCE_METRICS.map((metricKey, index) => (
                <MetricChartBox
                  key={metricKey}
                  data={metricsData}
                  interval={interval}
                  metric={metricKey}
                  height={200}
                  chartType="line"
                  className={twMerge(
                    'rounded-none! bg-transparent dark:bg-transparent',
                    index === 0 && 'lg:col-span-2',
                    'border-t-0 border-r border-b border-l-0 border-slate-200 shadow-none dark:border-slate-800',
                  )}
                />
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
