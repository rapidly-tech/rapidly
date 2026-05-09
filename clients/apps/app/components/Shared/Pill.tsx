/**
 * Compact status indicator with color-coded background.
 *
 * Supports green, yellow, red, and blue semantic colors. Accepts a
 * loading prop for skeleton shimmer states.
 */
import { Box } from '@/components/Shared/Box'
import { Text } from '@/components/Shared/Text'
import { useTheme } from '@/design-system/useTheme'
import { StyleProp, TextStyle, ViewStyle } from 'react-native'

type PillColor = 'green' | 'yellow' | 'red' | 'blue'

/** Maps a semantic color name to foreground + background token pairs. */
function resolveColorTokens(color: PillColor) {
  const mapping = {
    green: { text: 'statusGreen', bg: 'statusGreenBg' },
    yellow: { text: 'statusYellow', bg: 'statusYellowBg' },
    red: { text: 'statusRed', bg: 'statusRedBg' },
    blue: { text: 'statusBlue', bg: 'statusBlueBg' },
  } as const

  return mapping[color]
}

export const Pill = ({
  color,
  children,
  style,
  textStyle,
  loading,
}: {
  color: PillColor
  children: React.ReactNode
  style?: StyleProp<ViewStyle>
  textStyle?: StyleProp<TextStyle>
  loading?: boolean
}) => {
  const theme = useTheme()
  const tokens = resolveColorTokens(color)

  return (
    <Box
      paddingHorizontal="spacing-6"
      paddingVertical="spacing-4"
      borderRadius="border-radius-6"
      style={[{ backgroundColor: theme.colors[tokens.bg] }, style]}
    >
      <Text
        variant="caption"
        textTransform="capitalize"
        loading={loading}
        placeholderText={color}
        placeholderColor={tokens.bg}
        style={[{ color: theme.colors[tokens.text] }, textStyle]}
      >
        {children}
      </Text>
    </Box>
  )
}
