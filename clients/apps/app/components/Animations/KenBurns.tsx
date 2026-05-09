/**
 * Continuous Ken Burns (slow zoom) effect for background imagery.
 *
 * The child content gently scales between 1x and `maxScale` in an
 * infinite loop while fading in from transparent. Changing `trigger`
 * restarts both animations.
 */
import { PropsWithChildren, useEffect } from 'react'
import { ViewStyle } from 'react-native'
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withTiming,
} from 'react-native-reanimated'

interface Props extends PropsWithChildren {
  style?: ViewStyle
  duration?: number
  maxScale?: number
  trigger?: number
  fadeInDuration?: number
}

export function KenBurns({
  children,
  style,
  duration = 20000,
  maxScale = 1.08,
  trigger = 0,
  fadeInDuration = 1200,
}: Props) {
  const scaleVal = useSharedValue(1)
  const opacityVal = useSharedValue(0)

  useEffect(() => {
    // Fade in
    opacityVal.value = 0
    opacityVal.value = withTiming(1, {
      duration: fadeInDuration,
      easing: Easing.out(Easing.ease),
    })

    // Infinite zoom oscillation
    const halfDuration = duration / 2
    const easeFn = Easing.inOut(Easing.ease)

    scaleVal.value = 1
    scaleVal.value = withRepeat(
      withSequence(
        withTiming(maxScale, { duration: halfDuration, easing: easeFn }),
        withTiming(1, { duration: halfDuration, easing: easeFn }),
      ),
      -1,
      false,
    )
  }, [scaleVal, opacityVal, duration, maxScale, trigger, fadeInDuration])

  const animStyle = useAnimatedStyle(() => ({
    opacity: opacityVal.value,
    transform: [{ scale: scaleVal.value }],
  }))

  return (
    <Animated.View
      style={[
        {
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
        },
        style,
        animStyle,
      ]}
    >
      {children}
    </Animated.View>
  )
}
