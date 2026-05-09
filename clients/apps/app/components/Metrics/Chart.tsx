/**
 * Dual-line metric chart comparing the current period against the previous one.
 *
 * Renders a Victory Native CartesianChart with two overlaid Line paths,
 * plus a headline total, optional comparison total, and date-range labels.
 */
import { Box } from '@/components/Shared/Box'
import { Text } from '@/components/Shared/Text'
import { useTheme } from '@/design-system/useTheme'
import { toValueDataPoints, useMetrics } from '@/hooks/rapidly/metrics'
import { schemas } from '@rapidly-tech/client'
import { format } from 'date-fns'
import { useMemo } from 'react'
import { CartesianChart, Line } from 'victory-native'
import { getFormattedMetricValue } from './utils'

interface ChartProps {
  currentPeriodData: ReturnType<typeof useMetrics>['data']
  previousPeriodData: ReturnType<typeof useMetrics>['data']
  title?: string
  trend?: number
  height?: number
  showTotal?: boolean
  strokeWidth?: number
  showPreviousPeriodTotal?: boolean
  metric: schemas['Metric'] & { key: keyof schemas['MetricsTotals'] }
  currentPeriod: { startDate: Date; endDate: Date }
}

export const Chart = ({
  currentPeriodData,
  previousPeriodData,
  title,
  height = 80,
  strokeWidth = 2,
  showPreviousPeriodTotal = true,
  metric,
  currentPeriod,
}: ChartProps) => {
  const theme = useTheme()

  // Compute totals
  const currentTotal = currentPeriodData?.totals[metric.key] ?? 0
  const formattedCurrent = useMemo(
    () => getFormattedMetricValue(metric, currentTotal),
    [currentTotal, metric],
  )

  const previousTotal = previousPeriodData?.totals[metric.key]
  const formattedPrevious = useMemo(
    () =>
      previousTotal != null
        ? getFormattedMetricValue(metric, previousTotal)
        : null,
    [previousTotal, metric],
  )

  // Normalise data points into a single array for Victory
  const currentPoints = toValueDataPoints(currentPeriodData, metric.key)
  const previousPoints = toValueDataPoints(previousPeriodData, metric.key)

  const mergedData = useMemo(
    () =>
      currentPoints.map((pt, idx) => ({
        index: idx,
        current: pt.value,
        previous: previousPoints[idx]?.value ?? 0,
      })),
    [currentPoints, previousPoints],
  )

  const allValues = [
    ...currentPoints.map((d) => d.value),
    ...previousPoints.map((d) => d.value),
  ]
  const yMin = Math.min(...allValues, 0)
  const yMax = Math.max(...allValues, 1)

  return (
    <Box
      backgroundColor="card"
      padding="spacing-24"
      borderRadius="border-radius-24"
      gap="spacing-12"
    >
      <Box flexDirection="row" justifyContent="space-between">
        {title ? <Text variant="subtitle">{title}</Text> : null}
      </Box>

      <Box flexDirection="row" alignItems="baseline" gap="spacing-8">
        <Text variant="headlineXLarge">{formattedCurrent}</Text>
        {showPreviousPeriodTotal && formattedPrevious !== undefined ? (
          <Text color="subtext">{`vs. ${formattedPrevious}`}</Text>
        ) : null}
      </Box>

      {mergedData.length > 0 ? (
        <Box style={{ width: '100%', height }}>
          <CartesianChart
            data={mergedData}
            xKey="index"
            yKeys={['current', 'previous']}
            domain={{ y: [yMin, yMax] }}
            domainPadding={{ top: 4, bottom: 4 }}
            axisOptions={{
              lineColor: 'transparent',
              labelColor: 'transparent',
            }}
            frame={{ lineColor: 'transparent' }}
          >
            {({ points }) => (
              <>
                <Line
                  points={points.previous}
                  color={theme.colors.secondary}
                  strokeWidth={strokeWidth}
                  curveType="monotoneX"
                />
                <Line
                  points={points.current}
                  color={theme.colors.primary}
                  strokeWidth={strokeWidth}
                  curveType="monotoneX"
                />
              </>
            )}
          </CartesianChart>
        </Box>
      ) : null}

      <Box flexDirection="row" justifyContent="space-between">
        <Text variant="caption" color="subtext">
          {format(currentPeriod.startDate, 'MMM d')}
        </Text>
        <Text variant="caption" color="subtext" textAlign="right">
          {format(currentPeriod.endDate, 'MMM d')}
        </Text>
      </Box>
    </Box>
  )
}
