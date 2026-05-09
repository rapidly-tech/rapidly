/**
 * Gestural slide-to-confirm control.
 *
 * The user drags a circular thumb across a track. When the thumb reaches
 * the 90% threshold the action fires. Visual + haptic feedback guides the
 * user through the idle -> loading -> success lifecycle.
 */
import { useTheme } from '@/design-system/useTheme'
import * as Haptics from 'expo-haptics'
import { useCallback, useState } from 'react'
import { StyleProp, ViewStyle } from 'react-native'
import { Gesture, GestureDetector } from 'react-native-gesture-handler'
import { Iconify } from 'react-native-iconify'
import Animated, {
  Extrapolation,
  interpolate,
  interpolateColor,
  runOnJS,
  useAnimatedReaction,
  useAnimatedStyle,
  useSharedValue,
  withSequence,
  withSpring,
  withTiming,
} from 'react-native-reanimated'
import { Box } from './Box'

// Layout constants
const TRACK_HEIGHT = 80
const THUMB_DIAMETER = 64
const THUMB_INSET = 8
const ACTIVATION_RATIO = 0.9

// Timing constants
const MIN_LOADER_MS = 2000
const DONE_DISPLAY_MS = 2000

const resetSpring = { damping: 30, stiffness: 300, overshootClamping: true }

type Phase = 'idle' | 'loading' | 'success'

interface SlideToActionProps {
  onSlideComplete: () => Promise<void> | void
  onFinish?: () => void
  text?: string
  releaseText?: string
  successText?: string
  loadingText?: string
  style?: StyleProp<ViewStyle>
  disabled?: boolean
  onSlideStart?: () => void
  onSlideEnd?: () => void
}

export const SlideToAction = ({
  onSlideComplete,
  onFinish,
  text = 'Slide to confirm',
  releaseText = 'Release to confirm',
  successText = 'Success!',
  loadingText = 'Processing...',
  style,
  disabled = false,
  onSlideStart,
  onSlideEnd,
}: SlideToActionProps) => {
  const theme = useTheme()

  const [trackWidth, setTrackWidth] = useState(0)
  const [phase, setPhase] = useState<Phase>('idle')

  const progress = useSharedValue(0)
  const reachedThreshold = useSharedValue(false)
  const loaderFade = useSharedValue(0)
  const doneFade = useSharedValue(0)
  const thumbPulse = useSharedValue(1)

  const maxTravel = Math.max(0, trackWidth - THUMB_DIAMETER - THUMB_INSET * 2)

  // Haptic helpers
  const tapHaptic = useCallback(() => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light)
  }, [])

  const heavyHaptic = useCallback(() => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy)
  }, [])

  const enterLoading = useCallback(() => setPhase('loading'), [])
  const enterSuccess = useCallback(() => setPhase('success'), [])

  const executeAction = useCallback(async () => {
    const t0 = Date.now()
    await onSlideComplete()
    const remaining = MIN_LOADER_MS - (Date.now() - t0)
    if (remaining > 0) await new Promise((r) => setTimeout(r, remaining))
  }, [onSlideComplete])

  // Detect when the thumb crosses the activation boundary
  useAnimatedReaction(
    () => progress.value >= ACTIVATION_RATIO,
    (crossed, prev) => {
      if (crossed !== prev) {
        reachedThreshold.value = crossed
        if (crossed) {
          thumbPulse.value = withSequence(
            withTiming(1.25, { duration: 100 }),
            withTiming(1.1, { duration: 100 }),
          )
          runOnJS(heavyHaptic)()
        }
      }
    },
    [],
  )

  const onDragStart = useCallback(() => onSlideStart?.(), [onSlideStart])
  const onDragEnd = useCallback(() => onSlideEnd?.(), [onSlideEnd])

  const runAction = useCallback(async () => {
    enterLoading()
    loaderFade.value = withTiming(1, { duration: 300 })

    await executeAction()

    heavyHaptic()
    enterSuccess()
    loaderFade.value = withTiming(0, { duration: 200 })
    doneFade.value = withTiming(1, { duration: 300 })
    thumbPulse.value = withSequence(
      withTiming(1.3, { duration: 100 }),
      withTiming(1, { duration: 100 }),
    )

    await new Promise((r) => setTimeout(r, DONE_DISPLAY_MS))
    onFinish?.()
  }, [
    enterLoading,
    loaderFade,
    executeAction,
    heavyHaptic,
    enterSuccess,
    doneFade,
    thumbPulse,
    onFinish,
  ])

  // Pan gesture controlling the thumb
  const dragGesture = Gesture.Pan()
    .enabled(!disabled && phase === 'idle')
    .onStart(() => {
      thumbPulse.value = withSequence(
        withTiming(1.2, { duration: 100 }),
        withTiming(1.1, { duration: 100 }),
      )
      runOnJS(onDragStart)()
      runOnJS(tapHaptic)()
    })
    .onUpdate((e) => {
      if (maxTravel > 0) {
        progress.value = Math.max(0, Math.min(e.translationX / maxTravel, 1))
      }
    })
    .onEnd(() => {
      thumbPulse.value = withTiming(1, { duration: 150 })
      runOnJS(onDragEnd)()

      if (progress.value >= ACTIVATION_RATIO) {
        progress.value = withSpring(1, resetSpring)
        runOnJS(runAction)()
      } else {
        progress.value = withSpring(0, resetSpring)
      }
    })

  // -- Animated styles -------------------------------------------------------

  const thumbAnimStyle = useAnimatedStyle(() => {
    const tx = Math.max(0, progress.value * maxTravel)
    const t = Math.max(0, Math.min(1, progress.value))

    const slideColor = interpolateColor(
      t,
      [0, 0.15],
      [theme.colors.secondary, theme.colors.monochromeInverted],
    )
    const thresholdColor = interpolateColor(
      t,
      [0.89, 0.9],
      [theme.colors.monochromeInverted, theme.colors.primary],
    )
    const base = t >= 0.9 ? thresholdColor : slideColor

    const bg =
      doneFade.value > 0
        ? interpolateColor(
            doneFade.value,
            [0, 1],
            [base, theme.colors.statusGreen],
          )
        : base

    return {
      transform: [{ translateX: tx }, { scale: thumbPulse.value }],
      backgroundColor: bg,
    }
  })

  const idleTextStyle = useAnimatedStyle(() => {
    const o = interpolate(progress.value, [0, 0.7, 0.9], [1, 1, 0])
    const ty = interpolate(progress.value, [0, 0.7, 0.9], [0, 0, -15])
    return {
      opacity: loaderFade.value > 0 || doneFade.value > 0 ? 0 : o,
      transform: [{ translateY: ty }],
    }
  })

  const releaseTextStyle = useAnimatedStyle(() => {
    const o = interpolate(
      progress.value,
      [0, 0.7, 0.9],
      [0, 0, 1],
      Extrapolation.CLAMP,
    )
    const ty = interpolate(
      progress.value,
      [0, 0.7, 0.9],
      [15, 15, 0],
      Extrapolation.CLAMP,
    )
    return {
      opacity: loaderFade.value > 0 || doneFade.value > 0 ? 0 : o,
      transform: [{ translateY: ty }],
    }
  })

  const loadingTextStyle = useAnimatedStyle(() => {
    const o = interpolate(loaderFade.value, [0, 1], [0, 1])
    const ty = interpolate(loaderFade.value, [0, 1], [10, 0])
    return {
      opacity: doneFade.value > 0 ? 0 : o,
      transform: [{ translateY: ty }],
    }
  })

  const successTextStyle = useAnimatedStyle(() => {
    const o = interpolate(doneFade.value, [0, 1], [0, 1])
    const ty = interpolate(doneFade.value, [0, 1], [10, 0])
    return { opacity: o, transform: [{ translateY: ty }] }
  })

  const [iconColor, setIconColor] = useState<string>(
    theme.colors.monochromeInverted,
  )

  useAnimatedReaction(
    () => {
      const t = Math.max(0, Math.min(1, progress.value))

      const slideColor = interpolateColor(
        t,
        [0, 0.15],
        [theme.colors.monochromeInverted, theme.colors.monochrome],
      )
      const thresholdColor = interpolateColor(
        t,
        [0.89, 0.9],
        [theme.colors.monochrome, theme.colors.monochromeInverted],
      )
      const base = t >= 0.9 ? thresholdColor : slideColor

      return doneFade.value > 0
        ? interpolateColor(
            doneFade.value,
            [0, 1],
            [base, theme.colors.monochrome],
          )
        : base
    },
    (color) => {
      runOnJS(setIconColor)(color)
    },
    [],
  )

  // -- Render helpers --------------------------------------------------------

  const overlayBase = {
    position: 'absolute' as const,
    width: '100%' as const,
    height: '100%' as const,
    justifyContent: 'center' as const,
    alignItems: 'center' as const,
  }

  const trackLabelStyle = { fontSize: 16, fontWeight: '500' as const }

  return (
    <Box
      height={TRACK_HEIGHT}
      width="100%"
      borderRadius="border-radius-999"
      backgroundColor="card"
      overflow="hidden"
      style={style}
      onLayout={(e) => setTrackWidth(e.nativeEvent.layout.width)}
    >
      {/* Idle label */}
      <Animated.View style={[overlayBase, idleTextStyle]} pointerEvents="none">
        <Animated.Text
          style={{ ...trackLabelStyle, color: theme.colors.monochromeInverted }}
        >
          {text}
        </Animated.Text>
      </Animated.View>

      {/* Threshold label */}
      <Animated.View
        style={[overlayBase, releaseTextStyle]}
        pointerEvents="none"
      >
        <Animated.Text
          style={{ ...trackLabelStyle, color: theme.colors.monochromeInverted }}
        >
          {releaseText}
        </Animated.Text>
      </Animated.View>

      {/* Loading label */}
      <Animated.View
        style={[overlayBase, loadingTextStyle]}
        pointerEvents="none"
      >
        <Animated.Text
          style={{ ...trackLabelStyle, color: theme.colors.monochromeInverted }}
        >
          {loadingText}
        </Animated.Text>
      </Animated.View>

      {/* Success label */}
      <Animated.View
        style={[overlayBase, successTextStyle]}
        pointerEvents="none"
      >
        <Animated.Text
          style={{
            ...trackLabelStyle,
            fontWeight: '600',
            color: theme.colors.statusGreen,
          }}
        >
          {successText}
        </Animated.Text>
      </Animated.View>

      {/* Draggable thumb */}
      <GestureDetector gesture={dragGesture}>
        <Animated.View
          style={[
            {
              position: 'absolute',
              height: THUMB_DIAMETER,
              width: THUMB_DIAMETER,
              left: THUMB_INSET,
              top: THUMB_INSET,
              borderRadius: THUMB_DIAMETER / 2,
              justifyContent: 'center',
              alignItems: 'center',
            },
            thumbAnimStyle,
          ]}
        >
          <Iconify
            icon={
              phase === 'success'
                ? 'solar:check-read-linear'
                : 'solar:alt-arrow-right-linear'
            }
            size={phase === 'success' ? 24 : 18}
            color={iconColor}
          />
        </Animated.View>
      </GestureDetector>
    </Box>
  )
}
