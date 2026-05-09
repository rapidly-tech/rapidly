/**
 * Entrance animation that combines a vertical slide with a fade-in.
 *
 * Content starts 20 points below its final position and at zero opacity,
 * then springs into view after an optional delay. Changing the `trigger`
 * prop replays the animation.
 */
import { PropsWithChildren, useEffect } from 'react'
import Animated, {
  interpolate,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withSpring,
  WithSpringConfig,
} from 'react-native-reanimated'

interface Props extends PropsWithChildren {
  delay?: number
  withSpringProps?: WithSpringConfig
  trigger?: number
}

const DEFAULT_SPRING: WithSpringConfig = {
  stiffness: 200,
  damping: 120,
  mass: 4,
}

export function FadeInAndUp({
  children,
  delay = 0,
  withSpringProps = DEFAULT_SPRING,
  trigger = 0,
}: Props) {
  const animProgress = useSharedValue(0)

  useEffect(() => {
    // Reset then animate on each trigger change
    animProgress.value = 0
    animProgress.value = withDelay(delay, withSpring(1, withSpringProps))
  }, [delay, animProgress, withSpringProps, trigger])

  const style = useAnimatedStyle(() => ({
    opacity: animProgress.value,
    transform: [
      { translateY: interpolate(animProgress.value, [0, 1], [20, 0]) },
    ],
  }))

  return <Animated.View style={style}>{children}</Animated.View>
}
