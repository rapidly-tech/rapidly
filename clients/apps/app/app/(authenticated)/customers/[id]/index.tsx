import { Avatar } from '@/components/Shared/Avatar'
import { Box } from '@/components/Shared/Box'
import { DetailRow, Details } from '@/components/Shared/Details'
import { Text } from '@/components/Shared/Text'
import { useTheme } from '@/design-system/useTheme'
import { useCustomer } from '@/hooks/rapidly/customers'
import { useMetrics } from '@/hooks/rapidly/metrics'
import { WorkspaceContext } from '@/providers/WorkspaceProvider'
import { formatCurrency } from '@rapidly-tech/currency'
import { Stack, useLocalSearchParams } from 'expo-router'
import React, { useCallback, useContext, useMemo } from 'react'
import { RefreshControl, ScrollView } from 'react-native'

export default function Index() {
  const { workspace } = useContext(WorkspaceContext)
  const { id } = useLocalSearchParams()
  const theme = useTheme()

  const {
    data: customer,
    refetch: refetchCustomer,
    isRefetching: isCustomerRefetching,
  } = useCustomer(workspace?.id, id as string)

  const startDate = useMemo(() => {
    return new Date(customer?.created_at ?? new Date())
  }, [customer])

  const endDate = useMemo(() => {
    return new Date()
  }, [])

  const {
    data: metrics,
    refetch: refetchMetrics,
    isRefetching: isMetricsRefetching,
  } = useMetrics(workspace?.id, startDate, endDate, {
    interval: 'month',
    customer_id: [id as string],
  })

  const isRefetching = isCustomerRefetching || isMetricsRefetching

  const refetch = useCallback(() => {
    return Promise.allSettled([refetchCustomer(), refetchMetrics()])
  }, [refetchCustomer, refetchMetrics])

  const totalRevenue = useMemo(() => {
    if (!metrics?.periods.length) return 0
    return metrics.periods.reduce(
      (sum, p) => sum + (p.file_share_revenue ?? 0),
      0,
    )
  }, [metrics])

  return (
    <>
      <Stack.Screen
        options={{
          title: customer?.name ?? 'Customer',
        }}
      />
      <ScrollView
        style={{ flex: 1, padding: theme.spacing['spacing-16'] }}
        refreshControl={
          <RefreshControl onRefresh={refetch} refreshing={isRefetching} />
        }
        contentContainerStyle={{
          flexDirection: 'column',
          gap: theme.spacing['spacing-24'],
          paddingBottom: theme.spacing['spacing-48'],
        }}
      >
        <Box flexDirection="column" alignItems="center" gap="spacing-24">
          <Avatar
            image={customer?.avatar_url}
            name={customer?.name ?? customer?.email ?? ''}
            size={120}
          />
          <Box alignItems="center" flexDirection="column" gap="spacing-6">
            <Text variant="titleLarge" style={{ fontWeight: '600' }}>
              {customer?.name ?? '\u2014'}
            </Text>
            <Text color="subtext">{customer?.email}</Text>
          </Box>
        </Box>

        <Box flexDirection="row" gap="spacing-12">
          <Box
            backgroundColor="card"
            padding="spacing-12"
            borderRadius="border-radius-12"
            flex={1}
            gap="spacing-8"
          >
            <Text color="subtext">Revenue</Text>
            <Text>{formatCurrency(totalRevenue, 'usd')}</Text>
          </Box>
          <Box
            backgroundColor="card"
            padding="spacing-12"
            borderRadius="border-radius-12"
            flex={1}
            gap="spacing-8"
          >
            <Text color="subtext">First Seen</Text>
            <Text>
              {new Date(customer?.created_at ?? '').toLocaleDateString(
                'en-US',
                {
                  year: 'numeric',
                  month: 'short',
                  day: 'numeric',
                },
              )}
            </Text>
          </Box>
        </Box>

        <Box>
          <Details>
            <DetailRow
              label="Address"
              value={customer?.billing_address?.line1}
            />
            <DetailRow
              label="Address 2"
              value={customer?.billing_address?.line2}
            />
            <DetailRow label="City" value={customer?.billing_address?.city} />
            <DetailRow label="State" value={customer?.billing_address?.state} />
            <DetailRow
              label="Postal Code"
              value={customer?.billing_address?.postal_code}
            />
            <DetailRow
              label="Country"
              value={customer?.billing_address?.country}
            />
          </Details>
        </Box>

        {customer?.metadata && Object.keys(customer.metadata).length > 0 ? (
          <Box>
            <Details>
              {Object.entries(customer.metadata).map(([key, value]) => (
                <DetailRow key={key} label={key} value={String(value)} />
              ))}
            </Details>
          </Box>
        ) : null}
      </ScrollView>
    </>
  )
}
