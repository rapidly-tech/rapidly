/**
 * Auto-hiding header for the home feed.
 *
 * Tracks scroll position and direction to smoothly collapse/expand the
 * header. Also responds to high-velocity flings to snap the header
 * open when scrolling up quickly.
 */
import { NotificationBadge } from '@/components/Notifications/NotificationBadge'
import { Box } from '@/components/Shared/Box'
import RapidlyLogo from '@/components/Shared/RapidlyLogo'
import { Touchable } from '@/components/Shared/Touchable'
import { useTheme } from '@/design-system/useTheme'
import { useHomeHeaderHeight } from '@/hooks/useHomeHeaderHeight'
import { useAnimatedScroll } from '@/providers/AnimatedScrollProvider'
import { Link } from 'expo-router'
import React, { FC } from 'react'
import { Platform } from 'react-native'
import { Iconify } from 'react-native-iconify'
import Animated, {
  Extrapolation,
  interpolate,
  useAnimatedStyle,
  useDerivedValue,
  useSharedValue,
  withTiming,
} from 'react-native-reanimated'
import { useSafeAreaInsets } from 'react-native-safe-area-context'

const ANIM_DURATION_MS = 150

export const AnimatedHeader: FC = () => {
  const { netHeaderHeight } = useHomeHeaderHeight()
  const theme = useTheme()
  const insets = useSafeAreaInsets()

  const {
    offsetY,
    velocityOnEndDrag,
    headerTop,
    isHeaderVisible,
    scrollDirection,
    offsetYAnchorOnBeginDrag,
  } = useAnimatedScroll()

  const headerAlpha = useSharedValue(1)
  const bypassTopRange = useSharedValue(false)

  const nearTopOfList = useDerivedValue(
    () => offsetY.value < netHeaderHeight * 3,
  )
  const flingDetected = useDerivedValue(
    () => Math.abs(velocityOnEndDrag.value) > 1.25,
  )

  // Position animation
  const positionStyle = useAnimatedStyle(() => {
    if (offsetY.get() <= 0 && bypassTopRange.get()) {
      bypassTopRange.set(false)
    }

    // Near top: interpolate header position from scroll offset directly
    if (nearTopOfList.get() && !bypassTopRange.get()) {
      headerTop.set(
        interpolate(
          offsetY.value,
          [0, netHeaderHeight],
          [0, -netHeaderHeight],
          Extrapolation.CLAMP,
        ),
      )
    }

    // Away from top: react to velocity & direction
    if (!nearTopOfList.get()) {
      if (
        !isHeaderVisible.get() &&
        flingDetected.get() &&
        scrollDirection.get() === 'to-top'
      ) {
        headerTop.set(withTiming(0, { duration: ANIM_DURATION_MS }))
        bypassTopRange.set(true)
      }

      if (isHeaderVisible.get() && !flingDetected.get()) {
        headerTop.set(
          interpolate(
            offsetY.value,
            [
              offsetYAnchorOnBeginDrag.get(),
              offsetYAnchorOnBeginDrag.get() + netHeaderHeight,
            ],
            [0, -netHeaderHeight],
            Extrapolation.CLAMP,
          ),
        )
      }
    }

    return { top: headerTop.value }
  })

  // Opacity animation (mirrors position logic)
  const opacityStyle = useAnimatedStyle(() => {
    if (nearTopOfList.get() && !bypassTopRange.get()) {
      headerAlpha.set(
        interpolate(
          offsetY.value,
          [0, netHeaderHeight * 0.75],
          [1, 0],
          Extrapolation.CLAMP,
        ),
      )
    }

    if (!nearTopOfList.get()) {
      if (
        !isHeaderVisible.get() &&
        flingDetected.get() &&
        scrollDirection.get() === 'to-top'
      ) {
        headerAlpha.set(withTiming(1, { duration: ANIM_DURATION_MS }))
      }

      if (isHeaderVisible.get() && !flingDetected.get()) {
        headerAlpha.set(
          interpolate(
            offsetY.value,
            [
              offsetYAnchorOnBeginDrag.get(),
              offsetYAnchorOnBeginDrag.get() + netHeaderHeight,
            ],
            [1, 0],
            Extrapolation.CLAMP,
          ),
        )
      }
    }

    return { opacity: headerAlpha.value }
  })

  const topPadding = Platform.select({
    ios: insets.top,
    android: insets.top + theme.spacing['spacing-12'],
  })

  return (
    <Animated.View
      style={[
        {
          position: 'absolute',
          left: 0,
          right: 0,
          backgroundColor: theme.colors['background-regular'],
          zIndex: 50,
          paddingTop: topPadding,
        },
        positionStyle,
      ]}
    >
      <Animated.View
        style={[
          {
            flexDirection: 'row',
            alignItems: 'center',
            justifyContent: 'space-between',
            height: netHeaderHeight,
            paddingHorizontal: theme.spacing['spacing-16'],
            paddingBottom: theme.spacing['spacing-12'],
          },
          opacityStyle,
        ]}
      >
        <RapidlyLogo size={36} />
        <Box flexDirection="row" gap="spacing-20">
          <NotificationBadge />
          <Link href="/settings" asChild>
            <Touchable hitSlop={16}>
              <Iconify
                icon="solar:settings-linear"
                size={24}
                color={theme.colors['foreground-regular']}
              />
            </Touchable>
          </Link>
        </Box>
      </Animated.View>
    </Animated.View>
  )
}
