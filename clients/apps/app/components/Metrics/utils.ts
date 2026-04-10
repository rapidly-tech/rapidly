/**
 * Formatting and date-range utilities for the metrics module.
 *
 * Provides helpers to format metric values (scalar, currency, percentage),
 * determine the appropriate chart interval for a date range, and build
 * preset time-range objects.
 */
import { schemas } from '@rapidly-tech/client'
import { formatCurrency } from '@rapidly-tech/currency'
import {
  differenceInDays,
  differenceInMonths,
  differenceInWeeks,
  differenceInYears,
  subDays,
  subHours,
  subMonths,
} from 'date-fns'

const scalarFmt = Intl.NumberFormat('en-US', {})
const percentFmt = Intl.NumberFormat('en-US', { style: 'percent' })

/** Formats a raw metric value according to its declared type. */
export const getFormattedMetricValue = (
  metric: schemas['Metric'],
  value: number,
): string | undefined => {
  if (metric.type === 'scalar') return scalarFmt.format(value)
  if (metric.type === 'currency') return formatCurrency(value, 'usd')
  if (metric.type === 'percentage') return percentFmt.format(value)
  return undefined
}

/** Selects the most appropriate interval granularity for a given date range. */
export const dateRangeToInterval = (
  startDate: Date,
  endDate: Date,
): 'year' | 'month' | 'week' | 'day' | 'hour' => {
  const years = differenceInYears(endDate, startDate)
  const months = differenceInMonths(endDate, startDate)
  const weeks = differenceInWeeks(endDate, startDate)
  const days = differenceInDays(endDate, startDate)

  if (years >= 3) return 'year'
  if (months >= 4) return 'month'
  if (weeks > 4) return 'week'
  if (days > 1) return 'day'
  return 'hour'
}

/** Named time range presets anchored to the workspace creation date. */
export const timeRange = (workspace: schemas['Workspace']) =>
  ({
    '24h': {
      startDate: subDays(new Date(), 1),
      endDate: new Date(),
      title: '24h',
      description: 'Last 24 hours',
    },
    '30d': {
      startDate: subDays(new Date(), 30),
      endDate: new Date(),
      title: '30d',
      description: 'Last 30 days',
    },
    '3m': {
      startDate: subMonths(new Date(), 3),
      endDate: new Date(),
      title: '3m',
      description: 'Last 3 months',
    },
    all_time: {
      startDate: new Date(workspace.created_at),
      endDate: new Date(),
      title: 'All Time',
      description: 'All time',
    },
  }) as const

/** Builds previous-period equivalents for comparison charting. */
export const getPreviousParams = (
  startDate: Date,
): Omit<ReturnType<typeof timeRange>, 'all_time'> => ({
  '24h': {
    startDate: subHours(startDate, 24),
    endDate: startDate,
    title: '24h',
    description: 'Last 24 hours',
  },
  '30d': {
    startDate: subDays(startDate, 30),
    endDate: startDate,
    title: '30d',
    description: 'Last 30 days',
  },
  '3m': {
    startDate: subMonths(startDate, 3),
    endDate: startDate,
    title: '3m',
    description: 'Last 3 months',
  },
})
