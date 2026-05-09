import { Box as MetricsBox } from '@/components/Metrics/Box'
import { Banner } from '@/components/Shared/Banner'
import { Box } from '@/components/Shared/Box'
import { useTheme } from '@/design-system/useTheme'
import { useMetrics } from '@/hooks/rapidly/metrics'
import { useShare, useShareUpdate } from '@/hooks/rapidly/shares'
import { WorkspaceContext } from '@/providers/WorkspaceProvider'
import { schemas } from '@rapidly-tech/client'
import { formatCurrency } from '@rapidly-tech/currency'
import { Stack, useLocalSearchParams } from 'expo-router'
import { useContext, useMemo } from 'react'
import { RefreshControl, ScrollView } from 'react-native'

export interface ShareFullMediasMixin {
  full_medias: schemas['ShareMediaFileRead'][]
}

export default function Index() {
  const { id } = useLocalSearchParams()
  const theme = useTheme()
  const { workspace } = useContext(WorkspaceContext)

  const {
    data: share,
    refetch,
    isRefetching,
  } = useShare(workspace?.id, id as string)

  const now = useMemo(() => new Date(), [])

  const { data: metrics } = useMetrics(
    workspace?.id,
    new Date(workspace?.created_at ?? ''),
    now,
    {
      share_id: id as string,
      interval: 'month',
    },
  )

  const updateShare = useShareUpdate(workspace?.id, id as string)

  const { error: mutationError } = updateShare

  if (mutationError) {
    throw mutationError
  }

  if (!share) {
    return (
      <Stack.Screen
        options={{
          title: 'Share',
        }}
      />
    )
  }

  const totalSessions =
    metrics?.periods.reduce(
      (acc, period) => acc + (period.file_share_sessions ?? 0),
      0,
    ) ?? 0

  const lastPeriod = metrics?.periods[metrics.periods.length - 1]
  const cumulativeRevenue = lastPeriod?.cumulative_file_share_platform_fees ?? 0

  return (
    <ScrollView
      style={{
        flex: 1,
        padding: theme.spacing['spacing-16'],
        backgroundColor: theme.colors.background,
      }}
      contentContainerStyle={{
        flexDirection: 'column',
        gap: theme.spacing['spacing-32'],
        paddingBottom: theme.spacing['spacing-48'],
      }}
      refreshControl={
        <RefreshControl onRefresh={refetch} refreshing={isRefetching} />
      }
    >
      <Stack.Screen
        options={{
          title: share.name,
        }}
      />

      {share.is_archived ? (
        <Banner
          title="This share is archived"
          description="This share cannot be sold to new customers."
        />
      ) : null}

      <Box flexDirection="row" gap="spacing-16">
        <MetricsBox label="Sessions" value={totalSessions.toString()} />
        <MetricsBox
          label="Revenue"
          value={formatCurrency(cumulativeRevenue, 'usd')}
        />
      </Box>
    </ScrollView>
  )
}
