import { Box } from '@/components/Shared/Box'
import { Text } from '@/components/Shared/Text'
import { ShareRow } from '@/components/Shares/ShareRow'
import { useTheme } from '@/design-system/useTheme'
import { useInfiniteShares } from '@/hooks/rapidly/shares'
import { WorkspaceContext } from '@/providers/WorkspaceProvider'
import { schemas } from '@rapidly-tech/client'
import { FlashList } from '@shopify/flash-list'
import { Stack } from 'expo-router'
import React, { useContext, useMemo } from 'react'
import { RefreshControl } from 'react-native'

function SharesList() {
  const { workspace } = useContext(WorkspaceContext)
  const theme = useTheme()
  const { data, refetch, isRefetching, fetchNextPage, hasNextPage, isLoading } =
    useInfiniteShares(workspace?.id)

  const flatData = useMemo(() => {
    return (
      data?.pages
        .flatMap((page) => page.data)
        .sort((a, b) => (a.is_archived ? 1 : -1) - (b.is_archived ? 1 : -1)) ??
      []
    )
  }, [data])

  if (!workspace) {
    return null
  }

  return (
    <FlashList
      data={flatData}
      renderItem={({ item }: { item: schemas['Share'] }) => (
        <ShareRow
          share={item}
          currency={workspace.default_presentment_currency}
        />
      )}
      contentContainerStyle={{
        padding: theme.spacing['spacing-16'],
        backgroundColor: theme.colors.background,
        flexGrow: 1,
        paddingBottom: theme.spacing['spacing-32'],
      }}
      ListEmptyComponent={
        isLoading ? null : (
          <Box flex={1} justifyContent="center" alignItems="center">
            <Text color="subtext">No Shares</Text>
          </Box>
        )
      }
      ItemSeparatorComponent={() => <Box padding="spacing-4" />}
      keyExtractor={(item) => item.id}
      refreshControl={
        <RefreshControl onRefresh={refetch} refreshing={isRefetching} />
      }
      onEndReached={() => {
        if (hasNextPage) {
          fetchNextPage()
        }
      }}
      onEndReachedThreshold={0.8}
    />
  )
}

export default function Index() {
  return (
    <>
      <Stack.Screen options={{ title: 'Shares' }} />
      <SharesList />
    </>
  )
}
