/**
 * Collapsible content section with a tappable header row.
 *
 * Tap the header to expand or collapse the child content. Renders a
 * chevron indicator that flips direction based on the current state.
 */
import { Box } from '@/components/Shared/Box'
import { useTheme } from '@/design-system/useTheme'
import { useState } from 'react'
import { Iconify } from 'react-native-iconify'
import { Text } from './Text'
import { Touchable } from './Touchable'

export interface AccordionProps {
  title: string
  defaultOpen?: boolean
  children: React.ReactNode
}

export const Accordion = ({
  title,
  children,
  defaultOpen = false,
}: AccordionProps) => {
  const [expanded, setExpanded] = useState(defaultOpen)
  const theme = useTheme()

  const toggleExpanded = () => setExpanded((prev) => !prev)

  const chevronIcon = expanded
    ? 'solar:alt-arrow-up-linear'
    : 'solar:alt-arrow-down-linear'

  return (
    <Box flex={1} flexDirection="column" gap="spacing-12">
      <Touchable
        style={{
          flexDirection: 'row',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: theme.spacing['spacing-8'],
          paddingVertical: theme.spacing['spacing-12'],
          paddingHorizontal: theme.spacing['spacing-16'],
          borderRadius: theme.borderRadii['border-radius-12'],
          backgroundColor: theme.colors.card,
        }}
        onPress={toggleExpanded}
        activeOpacity={0.6}
      >
        <Text>{title}</Text>
        <Iconify
          icon={chevronIcon}
          size={24}
          color={theme.colors.monochromeInverted}
        />
      </Touchable>

      {expanded ? children : null}
    </Box>
  )
}
