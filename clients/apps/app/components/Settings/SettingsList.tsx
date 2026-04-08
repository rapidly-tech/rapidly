/**
 * Generic settings list with static and interactive item variants.
 *
 * SettingsItem delegates to an internal StaticRow or InteractiveRow
 * depending on the variant. Interactive rows show a trailing icon
 * (chevron, expand, or outward arrow) determined by the variant type.
 */
import { useTheme } from '@/design-system/useTheme'
import { PropsWithChildren, useMemo } from 'react'
import { Iconify } from 'react-native-iconify'
import { Box } from '../Shared/Box'
import { Text } from '../Shared/Text'
import { Touchable } from '../Shared/Touchable'

// -- Public prop types -------------------------------------------------------

type BaseProps = PropsWithChildren<{
  title: string
  description?: string
}>

interface StaticItemProps extends BaseProps {
  variant: 'static'
}

interface InteractiveItemProps extends BaseProps {
  variant: 'navigate' | 'select' | 'link'
  onPress: () => void
}

export type SettingsItemProps = StaticItemProps | InteractiveItemProps

// -- Internal row components -------------------------------------------------

function StaticRow({ title, description, children }: StaticItemProps) {
  return (
    <Box
      flexDirection="row"
      gap="spacing-4"
      justifyContent="space-between"
      alignItems={description ? 'flex-start' : 'center'}
      paddingVertical="spacing-8"
    >
      <Box flexDirection="column" gap="spacing-2" maxWidth="80%">
        <Text variant="body">{title}</Text>
        {description ? (
          <Text variant="bodySmall" color="subtext">
            {description}
          </Text>
        ) : null}
      </Box>
      <Box flexDirection="row" alignItems="center" gap="spacing-12">
        {children}
      </Box>
    </Box>
  )
}

/** Maps variant type to its trailing Solar Linear icon name. */
function trailingIconName(variant: InteractiveItemProps['variant']): string {
  switch (variant) {
    case 'navigate':
      return 'solar:alt-arrow-right-linear'
    case 'select':
      return 'solar:sort-vertical-linear'
    case 'link':
      return 'solar:square-arrow-right-up-linear'
  }
}

function InteractiveRow({
  title,
  variant,
  onPress,
  description,
  children,
}: InteractiveItemProps) {
  const theme = useTheme()
  const iconName = useMemo(() => trailingIconName(variant), [variant])
  const iconSize = variant === 'link' ? 16 : 20

  return (
    <Touchable onPress={onPress}>
      <Box
        flexDirection="row"
        gap="spacing-4"
        alignItems={description ? 'flex-start' : 'center'}
        justifyContent="space-between"
        paddingVertical="spacing-8"
      >
        <Box flexDirection="column" gap="spacing-2" maxWidth="70%">
          <Text variant="body">{title}</Text>
          {description ? (
            <Text variant="bodySmall" color="subtext">
              {description}
            </Text>
          ) : null}
        </Box>
        <Box flexDirection="row" alignItems="center" gap="spacing-12">
          {children}
          <Iconify
            icon={iconName}
            size={iconSize}
            color={theme.colors.subtext}
          />
        </Box>
      </Box>
    </Touchable>
  )
}

// -- Public component --------------------------------------------------------

export const SettingsItem = ({
  title,
  variant,
  description,
  children,
  ...rest
}: SettingsItemProps) => {
  if (variant === 'static') {
    return (
      <StaticRow title={title} variant={variant} description={description}>
        {children}
      </StaticRow>
    )
  }

  return (
    <InteractiveRow
      title={title}
      variant={variant}
      onPress={(rest as InteractiveItemProps).onPress}
      description={description}
    >
      {children}
    </InteractiveRow>
  )
}
