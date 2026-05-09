import { Chart } from '@/components/Metrics/Chart'
import {
  dateRangeToInterval,
  getPreviousParams,
  timeRange,
} from '@/components/Metrics/utils'
import { Box } from '@/components/Shared/Box'
import { Tabs, TabsList, TabsTrigger } from '@/components/Shared/Tabs'
import { useTheme } from '@/design-system/useTheme'
import { useMetrics } from '@/hooks/rapidly/metrics'
import { WorkspaceContext } from '@/providers/WorkspaceProvider'
import { schemas } from '@rapidly-tech/client'
import { FlashList } from '@shopify/flash-list'
import { Stack } from 'expo-router'
import React, { useContext, useMemo, useState } from 'react'
import { ActivityIndicator, RefreshControl, SafeAreaView } from 'react-native'

export default function Index() {
  const { workspace } = useContext(WorkspaceContext)
  const theme = useTheme()
  const [selectedTimeInterval, setSelectedTimeInterval] =
    useState<keyof ReturnType<typeof timeRange>>('30d')

  const { startDate, endDate } = useMemo(() => {
    if (!workspace) {
      return {
        startDate: new Date(),
        endDate: new Date(),
      }
    }

    return {
      startDate: timeRange(workspace)[selectedTimeInterval].startDate,
      endDate: timeRange(workspace)[selectedTimeInterval].endDate,
    }
  }, [selectedTimeInterval, workspace])

  const previousPeriod = useMemo(() => {
    const previousParams = getPreviousParams(startDate)

    if (selectedTimeInterval === 'all_time') {
      return null
    }

    return {
      startDate: previousParams[selectedTimeInterval].startDate,
      endDate: previousParams[selectedTimeInterval].endDate,
    }
  }, [selectedTimeInterval, startDate])

  const metrics = useMetrics(workspace?.id, startDate, endDate, {
    interval: dateRangeToInterval(startDate, endDate),
  })

  const previousMetrics = useMetrics(
    workspace?.id,
    previousPeriod?.startDate ?? startDate,
    previousPeriod?.endDate ?? endDate,
    {
      interval: dateRangeToInterval(
        previousPeriod?.startDate ?? startDate,
        previousPeriod?.endDate ?? endDate,
      ),
    },
    !!previousPeriod,
  )

  return (
    <>
      <Stack.Screen
        options={{
          title: 'Metrics',
        }}
      />
      <SafeAreaView style={{ margin: theme.spacing['spacing-16'] }}>
        <Tabs
          defaultValue={selectedTimeInterval}
          onValueChange={(value) =>
            setSelectedTimeInterval(value as keyof ReturnType<typeof timeRange>)
          }
        >
          {workspace ? (
            <TabsList>
              {Object.entries(timeRange(workspace)).map(([key, value]) => {
                return (
                  <TabsTrigger key={key} value={key}>
                    {value.title}
                  </TabsTrigger>
                )
              })}
            </TabsList>
          ) : null}
        </Tabs>
      </SafeAreaView>
      {metrics.isLoading ? (
        <Box flex={1} justifyContent="center" alignItems="center">
          <ActivityIndicator />
        </Box>
      ) : (
        <FlashList
          style={{ flex: 1 }}
          contentContainerStyle={{
            flexDirection: 'column',
            padding: theme.spacing['spacing-16'],
          }}
          ItemSeparatorComponent={() => <Box padding="spacing-8" />}
          data={
            Object.entries(metrics.data?.metrics ?? {}).map(
              ([metric, value]) => ({
                metric,
                value,
              }),
            ) as {
              metric: keyof schemas['MetricsTotals']
              value: schemas['Metric']
            }[]
          }
          renderItem={({ item }) => {
            return (
              <Chart
                key={item.metric}
                currentPeriodData={metrics.data}
                previousPeriodData={previousMetrics.data}
                title={item.value.display_name}
                metric={{
                  key: item.metric,
                  ...item.value,
                }}
                currentPeriod={{
                  startDate,
                  endDate,
                }}
                showPreviousPeriodTotal={selectedTimeInterval !== 'all_time'}
              />
            )
          }}
          keyExtractor={(item) => item.metric}
          refreshControl={
            <RefreshControl
              refreshing={metrics.isRefetching}
              onRefresh={metrics.refetch}
            />
          }
        />
      )}
    </>
  )
}
