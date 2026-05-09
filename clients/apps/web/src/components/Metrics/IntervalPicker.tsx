/**
 * IntervalPicker - time granularity selector for Rapidly analytics.
 *
 * Determines which intervals (hourly, daily, weekly, etc.) are valid
 * for a given date range and renders a dropdown to choose between them.
 */

import { enums, schemas } from '@rapidly-tech/client'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@rapidly-tech/ui/components/forms/Select'
import { differenceInDays } from 'date-fns'
import { useMemo } from 'react'

// ── Interval Boundary Definitions ──

type Interval = schemas['TimeInterval']

/** Upper bound (in days) for each interval granularity. */
const CEILING_DAYS: Record<Interval, number> = {
  hour: 7,
  day: 366,
  week: 365,
  month: 365 * 4,
  year: 365 * 10,
}

/** Lower bound (in days) for each interval granularity. */
const FLOOR_DAYS: Record<Interval, number> = {
  hour: 0,
  day: 0,
  week: 14,
  month: 60,
  year: 366,
}

// Ordered from coarsest to finest
const GRANULARITY_COARSE_TO_FINE: Interval[] = [
  'year',
  'month',
  'week',
  'day',
  'hour',
]

// ── Validation Helpers ──

/** Returns true when the given date span allows the specified interval. */
const isIntervalAllowed = (interval: Interval, daySpan: number): boolean =>
  daySpan >= FLOOR_DAYS[interval] && daySpan <= CEILING_DAYS[interval]

// ── Display Labels ──

const INTERVAL_LABELS: Record<Interval, string> = {
  hour: 'Hourly',
  day: 'Daily',
  week: 'Weekly',
  month: 'Monthly',
  year: 'Yearly',
}

// ── Exported Utility ──

/**
 * Given a current interval and a new date range, return the best-fit
 * interval. Keeps the current selection when still valid, otherwise
 * picks the closest valid granularity.
 */
export const getNextValidInterval = (
  current: Interval,
  startDate: Date,
  endDate: Date,
): Interval => {
  const span = differenceInDays(endDate, startDate)

  if (isIntervalAllowed(current, span)) return current

  // Search direction depends on whether the range grew or shrank
  const candidates =
    span > CEILING_DAYS[current]
      ? [...GRANULARITY_COARSE_TO_FINE].reverse() // range grew: try finer first
      : GRANULARITY_COARSE_TO_FINE // range shrank: try coarser first

  return candidates.find((iv) => isIntervalAllowed(iv, span)) ?? 'day'
}

// ── Component ──

interface IntervalPickerProps {
  interval: Interval
  onChange: (next: Interval) => void
  startDate?: Date
  endDate?: Date
}

const IntervalPicker = ({
  interval,
  onChange,
  startDate,
  endDate,
}: IntervalPickerProps) => {
  const unavailable = useMemo(() => {
    if (!startDate || !endDate) return new Set<Interval>()

    const span = differenceInDays(endDate, startDate)
    const blocked = new Set<Interval>()

    for (const iv of GRANULARITY_COARSE_TO_FINE) {
      if (!isIntervalAllowed(iv, span)) {
        blocked.add(iv)
      }
    }
    return blocked
  }, [startDate, endDate])

  return (
    <Select value={interval} onValueChange={onChange}>
      <SelectTrigger>
        <SelectValue placeholder="Select an interval" />
      </SelectTrigger>
      <SelectContent>
        {Object.values(enums.timeIntervalValues).map((iv) => (
          <SelectItem key={iv} value={iv} disabled={unavailable.has(iv)}>
            {INTERVAL_LABELS[iv]}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

export default IntervalPicker
