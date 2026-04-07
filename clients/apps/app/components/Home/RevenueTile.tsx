/**
 * Home dashboard tile showing 30-day cumulative revenue with a sparkline.
 *
 * Renders an animated line chart that draws in after data loads, plus a
 * formatted total at the bottom.
 */
import { Box } from '@/components/Shared/Box'
import { useTheme } from '@/design-system/useTheme'
import { useMetrics } from '@/hooks/rapidly/metrics'
import { WorkspaceContext } from '@/providers/WorkspaceProvider'
import { formatCurrency } from '@rapidly-tech/currency'
import { subMonths } from 'date-fns'
import { useContext, useEffect, useMemo } from 'react'
import { useSharedValue, withDelay, withTiming } from 'react-native-reanimated'
import { CartesianChart, Line } from 'victory-native'
import { Text } from '../Shared/Text'
import { Tile } from './Tile'

export interface RevenueTileProps {
  loading?: boolean
}

export const RevenueTile = ({ loading }: RevenueTileProps) => {
  const { workspace } = useContext(WorkspaceContext)
  const theme = useTheme()

  const rangeStart = useMemo(() => subMonths(new Date(), 1), [])
  const rangeEnd = useMemo(() => new Date(), [])

  const metrics = useMetrics(workspace?.id, rangeStart, rangeEnd, {
    interval: 'day',
  })

  // Build cumulative revenue series for the sparkline
  const cumulativeSeries = useMemo(() => {
    const periods = metrics.data?.periods ?? []
    let runningTotal = 0
    return periods.map((p, idx) => {
      runningTotal += p.file_share_revenue ?? 0
      return { value: runningTotal, index: idx }
    })
  }, [metrics])

  const peakValue = useMemo(() => {
    if (cumulativeSeries.length === 0) return 1
    return Math.max(...cumulativeSeries.map((d) => d.value), 1)
  }, [cumulativeSeries])

  // Animate the line drawing in
  const drawProgress = useSharedValue(0)

  useEffect(() => {
    if (cumulativeSeries.length > 0) {
      drawProgress.value = 0
      drawProgress.value = withDelay(500, withTiming(1, { duration: 800 }))
    }
  }, [cumulativeSeries.length, drawProgress])

  const totalRevenue = metrics.data?.totals.file_share_revenue ?? 0
  const formattedRevenue = formatCurrency(totalRevenue, 'usd')

  return (
    <Tile href="/metrics">
      <Box
        flex={1}
        flexDirection="column"
        justifyContent="space-between"
        gap="spacing-4"
      >
        <Box flexDirection="column" gap="spacing-4">
          <Box
            flexDirection="row"
            justifyContent="space-between"
            gap="spacing-4"
          >
            <Text variant="body" color="subtext">
              Revenue
            </Text>
          </Box>
          <Text variant="body">30 Days</Text>
        </Box>

        {cumulativeSeries.length > 0 ? (
          <Box flex={1} flexGrow={1} width="100%">
            <CartesianChart
              data={cumulativeSeries}
              xKey="index"
              yKeys={['value']}
              domain={{ y: [0, peakValue] }}
              domainPadding={{ bottom: 4, top: 4 }}
              axisOptions={{
                lineColor: 'transparent',
                labelColor: 'transparent',
              }}
              frame={{ lineColor: 'transparent' }}
            >
              {({ points }) => (
                <Line
                  points={points.value}
                  color={theme.colors.primary}
                  strokeWidth={2}
                  curveType="monotoneX"
                  end={drawProgress}
                />
              )}
            </CartesianChart>
          </Box>
        ) : null}

        <Text
          variant="headline"
          numberOfLines={1}
          loading={loading}
          placeholderText="$1,234"
        >
          {formattedRevenue}
        </Text>
      </Box>
    </Tile>
  )
}
