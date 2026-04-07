/**
 * Shimmer placeholder for skeleton loading states.
 *
 * Renders a rounded rectangle that pulses between low and medium opacity
 * on a 1-second loop to indicate loading activity.
 */
import { BorderRadiiToken, ColorToken } from '@/design-system/theme'
import { useTheme } from '@/design-system/useTheme'
import { useEffect } from 'react'
import { DimensionValue, ViewStyle } from 'react-native'
import Animated, {
  interpolate,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated'

interface PlaceholderBoxProps {
  width?: DimensionValue
  height?: number
  borderRadius?: BorderRadiiToken
  style?: ViewStyle
  color?: ColorToken
}

export const PlaceholderBox = ({
  width = '100%',
  height = 16,
  borderRadius = 'border-radius-4',
  style,
  color = 'secondary',
}: PlaceholderBoxProps) => {
  const theme = useTheme()
  const pulse = useSharedValue(0)

  useEffect(() => {
    pulse.value = withRepeat(withTiming(1, { duration: 1000 }), -1, false)
  }, [pulse])

  const animStyle = useAnimatedStyle(() => ({
    opacity: interpolate(pulse.value, [0, 0.5, 1], [0.3, 0.6, 0.3]),
  }))

  return (
    <Animated.View
      style={[
        { overflow: 'hidden' },
        {
          width,
          height,
          borderRadius: theme.borderRadii[borderRadius],
          backgroundColor: theme.colors[color],
        },
        animStyle,
        style,
      ]}
    />
  )
}
