/**
 * Animated toast notification rendered near the bottom of the screen.
 *
 * Slides up when visible and can be dismissed by swiping down. Supports
 * info, success, error, and warning variants with matching colors.
 * Persistent toasts include a close button.
 */
import { ColorToken } from '@/design-system/theme'
import { useTheme } from '@/design-system/useTheme'
import * as Haptics from 'expo-haptics'
import { useCallback, useEffect } from 'react'
import { Pressable } from 'react-native'
import { Gesture, GestureDetector } from 'react-native-gesture-handler'
import { Iconify } from 'react-native-iconify'
import Animated, {
  interpolate,
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withSpring,
  withTiming,
} from 'react-native-reanimated'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { Box } from './Box'
import { Text } from './Text'

export type ToastType = 'info' | 'success' | 'error' | 'warning'

interface ToastProps {
  message: string
  type: ToastType
  persistent: boolean
  visible: boolean
  onDismiss: () => void
  bottomOffset?: number
}

const DISMISS_THRESHOLD = 50

const springCfg = { damping: 60, stiffness: 600 }

interface TypeVisuals {
  bg: string
  iconTint: string
  textToken: ColorToken
}

/** Resolve visual tokens for a toast type. */
function visualsForType(
  type: ToastType,
  colors: ReturnType<typeof useTheme>['colors'],
): TypeVisuals {
  switch (type) {
    case 'success':
      return {
        bg: colors.statusGreen,
        iconTint: colors.monochrome,
        textToken: 'monochrome',
      }
    case 'error':
      return {
        bg: colors.statusRed,
        iconTint: colors.monochrome,
        textToken: 'monochrome',
      }
    case 'warning':
      return {
        bg: colors.statusYellow,
        iconTint: colors.monochrome,
        textToken: 'monochrome',
      }
    case 'info':
    default:
      return { bg: colors.card, iconTint: colors.text, textToken: 'text' }
  }
}

export const Toast = ({
  message,
  type,
  persistent,
  visible,
  onDismiss,
  bottomOffset = 0,
}: ToastProps) => {
  const theme = useTheme()
  const insets = useSafeAreaInsets()
  const visuals = visualsForType(type, theme.colors)

  const slideY = useSharedValue(100)
  const fadeIn = useSharedValue(0)
  const gestureY = useSharedValue(0)

  const hapticTap = useCallback(() => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light)
  }, [])

  useEffect(() => {
    if (visible) {
      slideY.value = withSpring(0, springCfg)
      fadeIn.value = withTiming(1, { duration: 200 })
    } else {
      slideY.value = withSpring(100, springCfg)
      fadeIn.value = withTiming(0, { duration: 150 })
    }
  }, [visible, slideY, fadeIn])

  const handleDismiss = useCallback(() => {
    hapticTap()
    onDismiss()
  }, [onDismiss, hapticTap])

  const swipeGesture = Gesture.Pan()
    .onUpdate((e) => {
      if (e.translationY > 0) {
        gestureY.value = e.translationY
      }
    })
    .onEnd((e) => {
      if (e.translationY > DISMISS_THRESHOLD || e.velocityY > 500) {
        runOnJS(handleDismiss)()
      }
      gestureY.value = withSpring(0, springCfg)
    })

  const containerStyle = useAnimatedStyle(() => {
    const combinedY = slideY.value + gestureY.value
    const gestureFade = interpolate(
      gestureY.value,
      [0, DISMISS_THRESHOLD],
      [1, 0.5],
    )
    return {
      transform: [{ translateY: combinedY }],
      opacity: fadeIn.value * gestureFade,
    }
  })

  return (
    <GestureDetector gesture={swipeGesture}>
      <Animated.View
        style={[
          {
            position: 'absolute',
            left: 0,
            right: 0,
            bottom: bottomOffset + insets.bottom + theme.spacing['spacing-16'],
            alignItems: 'center',
            zIndex: 9999,
          },
          containerStyle,
        ]}
      >
        <Box
          flexDirection="row"
          alignItems="center"
          paddingHorizontal="spacing-32"
          paddingVertical="spacing-12"
          borderRadius="border-radius-999"
          gap="spacing-12"
          style={{
            maxWidth: '90%',
            backgroundColor: visuals.bg,
            shadowColor: theme.colors.monochrome,
            shadowOffset: { width: 0, height: theme.dimension['dimension-4'] },
            shadowOpacity: 0.3,
            shadowRadius: theme.spacing['spacing-8'],
            elevation: 8,
          }}
        >
          <Text variant="body" color={visuals.textToken} numberOfLines={2}>
            {message}
          </Text>
          {persistent ? (
            <Pressable onPress={handleDismiss} hitSlop={8}>
              <Iconify
                icon="solar:close-circle-linear"
                size={20}
                color={theme.colors[visuals.textToken]}
              />
            </Pressable>
          ) : null}
        </Box>
      </Animated.View>
    </GestureDetector>
  )
}
