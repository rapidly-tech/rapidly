import { api } from '@/utils/client'
import { toISODate } from '@/utils/metrics'
import { operations, resolveResponse, schemas } from '@rapidly-tech/client'
import { UseQueryResult, useQuery } from '@tanstack/react-query'
import { baseRetry } from './retry'

// ── Types ──

export type ParsedMetricPeriod = schemas['MetricPeriod'] & {
  timestamp: Date
}

export interface ParsedMetricsResponse {
  periods: ParsedMetricPeriod[]
  totals: schemas['MetricsTotals']
  metrics: schemas['Metrics']
}

interface MetricsRequest {
  startDate: Date
  endDate: Date
  interval: schemas['TimeInterval']
  workspace_id?: string
  share_id?: string[]
  customer_id?: string[]
  metrics?: string[]
}

// ── Helpers ──

type TimezoneParam =
  operations['metrics:get']['parameters']['query']['timezone']

function detectTimezone(): TimezoneParam {
  return Intl.DateTimeFormat().resolvedOptions().timeZone as TimezoneParam
}

/**
 * Converts raw metric periods into typed objects whose `timestamp`
 * field is a real Date instead of an ISO string.
 */
function hydratePeriods(raw: schemas['MetricPeriod'][]): ParsedMetricPeriod[] {
  return raw.map((p) => ({
    ...p,
    timestamp: new Date(p.timestamp),
  })) as ParsedMetricPeriod[]
}

// ── Hook ──

/**
 * Fetches metrics for the specified date range, automatically resolving
 * the user's timezone and converting period timestamps to Date objects.
 */
export const useMetrics = (
  request: MetricsRequest,
  enabled: boolean = true,
): UseQueryResult<ParsedMetricsResponse, Error> => {
  const { startDate, endDate, ...filters } = request
  const tz = detectTimezone()

  const start = toISODate(startDate)
  const end = toISODate(endDate)

  return useQuery({
    queryKey: [
      'metrics',
      { startDate: start, endDate: end, timezone: tz, ...filters },
    ],
    queryFn: async () => {
      const raw = await resolveResponse(
        api.GET('/api/metrics/', {
          params: {
            query: {
              start_date: start,
              end_date: end,
              timezone: tz,
              ...filters,
            },
          },
        }),
      )

      return {
        ...raw,
        periods: hydratePeriods(raw.periods) as ParsedMetricPeriod[],
      }
    },
    retry: baseRetry,
    enabled,
  })
}
