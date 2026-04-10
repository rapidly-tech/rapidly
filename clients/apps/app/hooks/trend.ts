/**
 * Computes the revenue trend (percentage change) between two time intervals.
 *
 * Fetches metrics for both the current and previous intervals, sums up
 * cumulative revenue for each, and derives the percentage delta.
 */
import { WorkspaceContext } from '@/providers/WorkspaceProvider'
import { operations } from '@rapidly-tech/client'
import { useContext, useMemo } from 'react'
import { useMetrics } from './rapidly/metrics'

export const useRevenueTrend = (
  currentInterval: [Date, Date],
  previousInterval: [Date, Date],
  parameters: Omit<
    operations['metrics:get']['parameters']['query'],
    'start_date' | 'end_date'
  >,
) => {
  const { workspace } = useContext(WorkspaceContext)

  const currentMetrics = useMetrics(
    workspace?.id,
    currentInterval[0],
    currentInterval[1],
    parameters,
  )

  const previousMetrics = useMetrics(
    workspace?.id,
    previousInterval[0],
    previousInterval[1],
    parameters,
  )

  const currentPeriods = currentMetrics.data?.periods
  const previousPeriods = previousMetrics.data?.periods

  // Sum up period revenue
  const currentSum = currentPeriods?.reduce(
    (total, p) => total + (p.file_share_revenue ?? 0),
    0,
  )
  const previousSum = previousPeriods?.reduce(
    (total, p) => total + (p.file_share_revenue ?? 0),
    0,
  )

  const trend = useMemo(() => {
    if (!currentSum || !previousSum) return 0
    return (currentSum - previousSum) / previousSum
  }, [currentSum, previousSum])

  return {
    trend,
    currentCumulativeRevenue: currentSum ?? 0,
    previousCumulativeRevenue: previousSum ?? 0,
  }
}
