import { AnimatedHeader } from '@/components/Home/AnimatedHeader'
import { CatalogueTile } from '@/components/Home/CatalogueTile'
import { FinanceTile } from '@/components/Home/FinanceTile'
import { RevenueTile } from '@/components/Home/RevenueTile'
import { WorkspaceTile } from '@/components/Home/WorkspaceTile'
import { WorkspacesSheet } from '@/components/Settings/WorkspacesSheet'
import { Banner } from '@/components/Shared/Banner'
import { Box } from '@/components/Shared/Box'
import { Button } from '@/components/Shared/Button'
import { LinkList } from '@/components/Shared/LinkList'
import { useTheme } from '@/design-system/useTheme'
import { useCustomers } from '@/hooks/rapidly/customers'
import { useCreateNotificationRecipient } from '@/hooks/rapidly/notifications'
import { useHomeHeaderHeight } from '@/hooks/useHomeHeaderHeight'
import { useStoreReview } from '@/hooks/useStoreReview'
import {
  AnimatedScrollProvider,
  useAnimatedScroll,
} from '@/providers/AnimatedScrollProvider'
import { useNotifications } from '@/providers/NotificationsProvider'
import { WorkspaceContext } from '@/providers/WorkspaceProvider'
import { Stack } from 'expo-router'
import {
  checkForUpdateAsync,
  fetchUpdateAsync,
  reloadAsync,
  useUpdates,
} from 'expo-updates'
import React, { useCallback, useContext, useEffect, useState } from 'react'
import { RefreshControl } from 'react-native'
import { GestureHandlerRootView } from 'react-native-gesture-handler'
import Animated from 'react-native-reanimated'

export default function Index() {
  return (
    <AnimatedScrollProvider>
      <HomeContent />
    </AnimatedScrollProvider>
  )
}

function HomeContent() {
  const { workspace } = useContext(WorkspaceContext)
  const theme = useTheme()
  const { scrollHandler, scrollViewRef } = useAnimatedScroll()
  const { grossHeaderHeight } = useHomeHeaderHeight()

  const { isDownloading, isRestarting, isUpdateAvailable } = useUpdates()

  const {
    data: customers,
    refetch: refetchCustomers,
    isRefetching: isRefetchingCustomers,
  } = useCustomers(workspace?.id, {
    limit: 5,
  })

  const isRefetching = isRefetchingCustomers

  const refresh = useCallback(async () => {
    await refetchCustomers()
    try {
      await checkForUpdateAsync()
    } catch {
      // checkForUpdateAsync is not supported on simulator/emulator
    }
  }, [refetchCustomers])

  const { expoPushToken } = useNotifications()
  const { mutate: createNotificationRecipient } =
    useCreateNotificationRecipient()

  useEffect(() => {
    if (expoPushToken) {
      createNotificationRecipient(expoPushToken)
    }
  }, [expoPushToken, createNotificationRecipient])

  const { requestReview, shouldShow } = useStoreReview()

  useEffect(() => {
    if (shouldShow(false)) {
      const timer = setTimeout(() => {
        requestReview()
      }, 2000)
      return () => clearTimeout(timer)
    }
  }, [shouldShow, requestReview])

  async function onFetchUpdateAsync() {
    try {
      if (isUpdateAvailable) {
        await fetchUpdateAsync()
        await reloadAsync()
      }
    } catch (error) {
      alert(`Error fetching latest update: ${error}`)
    }
  }

  const [showWorkspacesSheet, setShowWorkspacesSheet] = useState(false)

  return (
    <GestureHandlerRootView>
      <Box flex={1} backgroundColor="background-regular">
        <Stack.Screen options={{ headerShown: false, title: 'Home' }} />
        <AnimatedHeader />
        <Animated.ScrollView
          ref={scrollViewRef}
          onScroll={scrollHandler}
          scrollEventThrottle={16}
          contentContainerStyle={{
            paddingTop: grossHeaderHeight,
            paddingBottom: theme.spacing['spacing-48'],
            backgroundColor: theme.colors['background-regular'],
            gap: theme.spacing['spacing-32'],
          }}
          refreshControl={
            <RefreshControl
              onRefresh={refresh}
              refreshing={isRefetching}
              progressViewOffset={grossHeaderHeight}
            />
          }
        >
          <Box
            padding="spacing-16"
            gap="spacing-32"
            flex={1}
            flexDirection="column"
          >
            {isUpdateAvailable ? (
              <Banner
                title="New Update Available"
                description="Update to the latest version to get the latest features and bug fixes"
              >
                <Button
                  onPress={onFetchUpdateAsync}
                  loading={isDownloading || isRestarting}
                >
                  Update
                </Button>
              </Banner>
            ) : null}
            <Box gap="spacing-16">
              <Box flexDirection="row" gap="spacing-16">
                <Box flex={1}>
                  <WorkspaceTile
                    onPress={() => setShowWorkspacesSheet(true)}
                    loading={!workspace}
                  />
                </Box>
                <Box flex={1}>
                  <RevenueTile loading={!workspace} />
                </Box>
              </Box>
              <Box flexDirection="row" gap="spacing-16">
                <Box flex={1}>
                  <CatalogueTile loading={!workspace} />
                </Box>
                <Box flex={1}>
                  <FinanceTile loading={!workspace} />
                </Box>
              </Box>
            </Box>

            <LinkList
              items={[
                {
                  title: 'Customers',
                  meta: `${customers?.pages[0].meta.total ?? 0}`,
                  link: '/customers',
                },
                {
                  title: 'File Shares',
                  link: '/products',
                },
              ]}
            />
          </Box>
        </Animated.ScrollView>

        {showWorkspacesSheet ? (
          <WorkspacesSheet onDismiss={() => setShowWorkspacesSheet(false)} />
        ) : null}
      </Box>
    </GestureHandlerRootView>
  )
}
