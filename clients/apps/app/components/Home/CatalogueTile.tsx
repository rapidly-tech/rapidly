/**
 * Home dashboard tile showing share count and a 7-day order streak.
 *
 * Fetches the workspace's share list and last-week metrics, rendering
 * small colored dots for each day where at least one order was placed.
 */
import { Box } from '@/components/Shared/Box'
import { useTheme } from '@/design-system/useTheme'
import { useMetrics } from '@/hooks/rapidly/metrics'
import { useShares } from '@/hooks/rapidly/shares'
import { WorkspaceContext } from '@/providers/WorkspaceProvider'
import { subDays } from 'date-fns'
import { useContext, useMemo } from 'react'
import { Text } from '../Shared/Text'
import { Tile } from './Tile'

export interface CatalogueTileProps {
  loading?: boolean
}

/** Pluralises "Share" based on count. */
function shareLabel(count: number): string {
  return `${count} ${count === 1 ? 'Share' : 'Shares'}`
}

export const CatalogueTile = ({ loading }: CatalogueTileProps) => {
  const theme = useTheme()
  const { workspace } = useContext(WorkspaceContext)

  const { data: shareData } = useShares(workspace?.id, { limit: 100 })

  const weekAgo = useMemo(() => subDays(new Date(), 6), [])
  const today = useMemo(() => new Date(), [])

  const metrics = useMetrics(workspace?.id, weekAgo, today, {
    interval: 'day',
  })

  const count = shareData?.data.length ?? 0

  return (
    <Tile href="/shares">
      <Box flex={1} flexDirection="column" justifyContent="space-between">
        <Box flexDirection="column" gap="spacing-4">
          <Text variant="body" color="subtext">
            Catalogue
          </Text>
          <Text variant="body" loading={loading} placeholderText="10 Shares">
            {shareLabel(count)}
          </Text>
        </Box>

        <Box flexDirection="column" gap="spacing-8">
          <Box
            flexDirection="row"
            justifyContent="space-between"
            gap="spacing-4"
          >
            <Text variant="body" color="subtext">
              Session Streak
            </Text>
          </Box>
          <Box
            flexDirection="row"
            justifyContent="space-between"
            gap="spacing-4"
          >
            {metrics.data?.periods.map((period) => {
              const hasSessions = (period.file_share_sessions ?? 0) > 0
              return (
                <Box
                  key={period.timestamp.toISOString()}
                  style={{
                    height: theme.dimension['dimension-10'],
                    width: theme.dimension['dimension-10'],
                    backgroundColor: hasSessions
                      ? theme.colors.primary
                      : theme.colors.border,
                    borderRadius: theme.borderRadii['border-radius-10'],
                  }}
                />
              )
            })}
          </Box>
        </Box>
      </Box>
    </Tile>
  )
}
