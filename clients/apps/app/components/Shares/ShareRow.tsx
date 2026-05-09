/**
 * List row for a share showing cover image, name, archive badge, and price.
 */
import { Box } from '@/components/Shared/Box'
import { Image } from '@/components/Shared/Image/Image'
import { useTheme } from '@/design-system/useTheme'
import { schemas } from '@rapidly-tech/client'
import { Link } from 'expo-router'
import React from 'react'
import { StyleProp, TextStyle } from 'react-native'
import { Iconify } from 'react-native-iconify'
import { Pill } from '../Shared/Pill'
import { Text } from '../Shared/Text'
import { Touchable } from '../Shared/Touchable'
import { SharePriceLabel } from './SharePriceLabel'

export interface ShareRowProps {
  share: schemas['Share']
  currency: string
  style?: StyleProp<TextStyle>
}

export const ShareRow = ({ share, currency, style }: ShareRowProps) => {
  const theme = useTheme()
  const coverUrl = share?.medias?.[0]?.public_url

  return (
    <Link
      href={`/shares/${share.id}`}
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
        <Box
          width={48}
          height={48}
          borderRadius="border-radius-8"
          overflow="hidden"
        >
          {coverUrl ? (
            <Image
              source={{ uri: coverUrl }}
              style={{ width: '100%', height: '100%' }}
              contentFit="cover"
            />
          ) : (
            <Box
              width="100%"
              height="100%"
              justifyContent="center"
              alignItems="center"
              borderColor="border"
              borderWidth={1}
              borderRadius="border-radius-8"
            >
              <Iconify
                icon="solar:gallery-minimalistic-linear"
                size={24}
                color={theme.colors.subtext}
              />
            </Box>
          )}
        </Box>

        <Box flex={1} flexDirection="column" gap="spacing-4">
          <Box
            flexDirection="row"
            gap="spacing-4"
            justifyContent="space-between"
          >
            <Text
              variant="bodyMedium"
              style={{ flexShrink: 1 }}
              numberOfLines={1}
              ellipsizeMode="tail"
            >
              {share.name}
            </Text>
            {share.is_archived ? <Pill color="red">Archived</Pill> : null}
          </Box>
          <SharePriceLabel share={share} currency={currency} />
        </Box>
      </Touchable>
    </Link>
  )
}
