/**
 * Wide card-style customer preview used in horizontal scroll lists.
 *
 * Shows the customer avatar, name, and email stacked vertically.
 * Tapping navigates to the customer detail screen.
 */
import { Box } from '@/components/Shared/Box'
import { useTheme } from '@/design-system/useTheme'
import { schemas } from '@rapidly-tech/client'
import { Link } from 'expo-router'
import React from 'react'
import { Dimensions } from 'react-native'
import { Avatar } from '../Shared/Avatar'
import { Text } from '../Shared/Text'
import { Touchable } from '../Shared/Touchable'

export interface CustomerCardProps {
  customer?: schemas['Customer']
  loading?: boolean
}

const CARD_WIDTH_RATIO = 0.66

export const CustomerCard = ({ customer, loading }: CustomerCardProps) => {
  const theme = useTheme()
  const cardWidth = Dimensions.get('screen').width * CARD_WIDTH_RATIO
  const displayName = customer?.name || customer?.email || ''

  return (
    <Link
      href={`/customers/${customer?.id}`}
      style={{
        paddingVertical: theme.spacing['spacing-32'],
        paddingHorizontal: theme.spacing['spacing-16'],
        flexDirection: 'column',
        alignItems: 'center',
        gap: theme.spacing['spacing-32'],
        borderRadius: theme.borderRadii['border-radius-16'],
        width: cardWidth,
        backgroundColor: theme.colors.card,
      }}
      asChild
    >
      <Touchable>
        <Avatar
          size={64}
          name={displayName}
          image={customer?.avatar_url ?? undefined}
          loading={loading}
        />
        <Box flexDirection="column" gap="spacing-8">
          <Text loading={loading} textAlign="center" placeholderText="John Doe">
            {customer?.name ?? '\u2014'}
          </Text>
          <Text
            variant="bodySmall"
            numberOfLines={1}
            ellipsizeMode="tail"
            textAlign="center"
            color="subtext"
            loading={loading}
            placeholderText="johndoe@example.com"
          >
            {customer?.email}
          </Text>
        </Box>
      </Touchable>
    </Link>
  )
}
