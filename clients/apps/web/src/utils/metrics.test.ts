import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  ALL_METRICS,
  fromISODate,
  getChartRangeParams,
  getFormattedMetricValue,
  getPreviousParams,
  getTimestampFormatter,
  toISODate,
  type ChartRange,
} from './metrics'

describe('toISODate / fromISODate', () => {
  it('toISODate produces YYYY-MM-DD in local timezone', () => {
    // Construct a date in local time. ``toISODate`` must return the
    // ``YYYY-MM-DD`` that matches what the user sees, not the UTC day.
    const d = new Date(2026, 3, 23, 12, 0, 0) // Apr 23 2026, 12:00 local
    expect(toISODate(d)).toBe('2026-04-23')
  })

  it('fromISODate returns a Date at midnight for the given day', () => {
    const d = fromISODate('2026-04-23')
    expect(d.getFullYear()).toBe(2026)
    expect(d.getMonth()).toBe(3) // April (0-indexed)
    expect(d.getDate()).toBe(23)
  })

  it('round-trips through toISODate → fromISODate → toISODate', () => {
    const original = '2026-01-15'
    expect(toISODate(fromISODate(original))).toBe(original)
  })
})

describe('getFormattedMetricValue', () => {
  it('formats scalar values via formatScalar', () => {
    const metric = { type: 'scalar' } as Parameters<
      typeof getFormattedMetricValue
    >[0]
    expect(getFormattedMetricValue(metric, 42)).toBe('42')
    expect(getFormattedMetricValue(metric, 1234)).toBe('1,234')
  })

  it('formats currency values with $ symbol', () => {
    const metric = { type: 'currency' } as Parameters<
      typeof getFormattedMetricValue
    >[0]
    expect(getFormattedMetricValue(metric, 500)).toContain('$')
  })

  it('formats percentage values with % suffix', () => {
    const metric = { type: 'percentage' } as Parameters<
      typeof getFormattedMetricValue
    >[0]
    expect(getFormattedMetricValue(metric, 0.25)).toMatch(/%$/)
  })

  it('formats currency_sub_cent with 4 fractional digits capability', () => {
    const metric = { type: 'currency_sub_cent' } as Parameters<
      typeof getFormattedMetricValue
    >[0]
    // 12 minor units → $0.1200 (4-digit formatter, partial-zero preserved)
    expect(getFormattedMetricValue(metric, 12)).toBe('$0.1200')
  })
})

describe('getTimestampFormatter', () => {
  const reference = new Date(2026, 3, 23, 14, 5, 0)

  it('formats hour with HH:MM', () => {
    const fmt = getTimestampFormatter('hour', 'en-US')
    expect(fmt(reference)).toMatch(/^\d{2}:\d{2}$/)
  })

  it('formats day with month + day', () => {
    const fmt = getTimestampFormatter('day', 'en-US')
    expect(fmt(reference)).toMatch(/Apr\s+23/)
  })

  it('formats week with month + day (same as day)', () => {
    const day = getTimestampFormatter('day', 'en-US')(reference)
    const week = getTimestampFormatter('week', 'en-US')(reference)
    expect(week).toBe(day)
  })

  it('formats month with month + year', () => {
    const fmt = getTimestampFormatter('month', 'en-US')
    expect(fmt(reference)).toMatch(/Apr\s+2026/)
  })

  it('formats year with 4-digit year', () => {
    const fmt = getTimestampFormatter('year', 'en-US')
    expect(fmt(reference)).toBe('2026')
  })
})

describe('getChartRangeParams', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 3, 23, 12, 0, 0))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('"today" range starts at start-of-day and ends now', () => {
    const [start, end, interval] = getChartRangeParams('today', new Date())
    expect(start.getHours()).toBe(0)
    expect(start.getDate()).toBe(23)
    expect(end.getTime()).toBeGreaterThanOrEqual(start.getTime())
    expect(interval).toBe('hour')
  })

  it('"30d" range uses day interval', () => {
    const [, , interval] = getChartRangeParams('30d', new Date())
    expect(interval).toBe('day')
  })

  it('"3m" range uses week or month interval (over a month of data)', () => {
    const [, , interval] = getChartRangeParams('3m', new Date())
    expect(['week', 'month']).toContain(interval)
  })

  it('"12m" range uses month interval', () => {
    const [, , interval] = getChartRangeParams('12m', new Date())
    expect(interval).toBe('month')
  })

  it('"all_time" range starts at createdAt', () => {
    const createdAt = new Date(2020, 0, 1)
    const [start] = getChartRangeParams('all_time', createdAt)
    expect(start.getTime()).toBe(createdAt.getTime())
  })

  it('"all_time" across >3 years gives year interval', () => {
    const createdAt = new Date(2020, 0, 1)
    const [, , interval] = getChartRangeParams('all_time', createdAt)
    expect(interval).toBe('year')
  })
})

describe('getPreviousParams', () => {
  const startDate = new Date(2026, 3, 23, 0, 0, 0)

  it('returns null for all_time (no previous window)', () => {
    expect(getPreviousParams(startDate, 'all_time')).toBeNull()
  })

  it('returns a window ending at startDate for "12m"', () => {
    const result = getPreviousParams(startDate, '12m')
    expect(result).not.toBeNull()
    expect(result![1].getTime()).toBe(startDate.getTime())
  })

  it('returns a window ending at startDate for "3m"', () => {
    const result = getPreviousParams(startDate, '3m')
    expect(result).not.toBeNull()
    expect(result![1].getTime()).toBe(startDate.getTime())
  })

  it('returns a window ending at startDate for "30d"', () => {
    const result = getPreviousParams(startDate, '30d')
    expect(result).not.toBeNull()
    expect(result![1].getTime()).toBe(startDate.getTime())
  })

  it('returns a window for "today" (yesterday to startDate)', () => {
    const result = getPreviousParams(startDate, 'today')
    expect(result).not.toBeNull()
    expect(result![1].getTime()).toBe(startDate.getTime())
    // ``startOfYesterday`` gives midnight of the previous day.
    expect(result![0].getHours()).toBe(0)
  })

  it('handles every documented ChartRange without throwing', () => {
    const ranges: ChartRange[] = ['all_time', '12m', '3m', '30d', 'today']
    for (const r of ranges) {
      expect(() => getPreviousParams(startDate, r)).not.toThrow()
    }
  })
})

describe('ALL_METRICS', () => {
  it('exposes an array of {slug, display_name} entries', () => {
    expect(Array.isArray(ALL_METRICS)).toBe(true)
    expect(ALL_METRICS.length).toBeGreaterThan(0)
    for (const m of ALL_METRICS) {
      expect(typeof m.slug).toBe('string')
      expect(typeof m.display_name).toBe('string')
      expect(m.slug.length).toBeGreaterThan(0)
      expect(m.display_name.length).toBeGreaterThan(0)
    }
  })

  it('has unique slugs', () => {
    const slugs = ALL_METRICS.map((m) => m.slug as string)
    expect(new Set(slugs).size).toBe(slugs.length)
  })

  it('includes core file-share metrics', () => {
    const slugs = ALL_METRICS.map((m) => m.slug as string)
    expect(slugs).toContain('file_share_sessions')
    expect(slugs).toContain('file_share_downloads')
    expect(slugs).toContain('file_share_revenue')
  })
})
