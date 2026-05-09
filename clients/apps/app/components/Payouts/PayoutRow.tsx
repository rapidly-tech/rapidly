/**
 * List row for a payout showing the amount, status pill, and date.
 */
import { Box } from '@/components/Shared/Box'
import { useTheme } from '@/design-system/useTheme'
import { Payout } from '@/hooks/rapidly/finance'
import { formatCurrency } from '@rapidly-tech/currency'
import { Link } from 'expo-router'
import React from 'react'
import { StyleProp, TextStyle } from 'react-native'
import { Pill } from '../Shared/Pill'
import { Text } from '../Shared/Text'
import { Touchable } from '../Shared/Touchable'

export interface PayoutRowProps {
  payout: Payout
  showTimestamp?: boolean
  style?: StyleProp<TextStyle>
}

const STATUS_COLORS = {
  pending: 'blue',
  in_transit: 'yellow',
  succeeded: 'green',
} as const

/** Turns "in_transit" into "in transit" for display. */
function humaniseStatus(status: string): string {
  return status.split('_').join(' ')
}

export const PayoutRow = ({ payout, style }: PayoutRowProps) => {
  const theme = useTheme()
  const formattedAmount = formatCurrency(payout.amount, payout.currency)
  const dateLabel = new Date(payout.created_at).toLocaleDateString('en-US', {
    dateStyle: 'medium',
  })

  return (
    <Link
      href={`/finance/${payout.id}`}
      style={[
        {
          padding: theme.spacing['spacing-16'],
          flexDirection: 'row',
          alignItems: 'center',
          borderRadius: theme.borderRadii['border-radius-12'],
          gap: theme.spacing['spacing-12'],
          backgroundColor: theme.colors.card,
        },
        style,
      ]}
      asChild
    >
      <Touchable>
        <Box flex={1} flexDirection="column" gap="spacing-4">
          <Box flexDirection="row" justifyContent="space-between">
            <Text variant="bodyMedium">{formattedAmount}</Text>
            <Pill color={STATUS_COLORS[payout.status]}>
              {humaniseStatus(payout.status)}
            </Pill>
          </Box>
          <Box flex={1} flexDirection="row" gap="spacing-6">
            <Text variant="bodySmall" color="subtext">
              {dateLabel}
            </Text>
          </Box>
        </Box>
      </Touchable>
    </Link>
  )
}
