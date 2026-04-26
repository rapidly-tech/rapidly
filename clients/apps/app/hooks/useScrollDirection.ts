/**
 * Reanimated worklet-compatible scroll direction tracker.
 *
 * Monitors whether the user is scrolling upward ("to-top"), downward
 * ("to-bottom"), or not at all ("idle"). Exposes additional anchor
 * values consumed by the AnimatedScrollProvider for header snap logic.
 */
import { SharedValue, useSharedValue } from 'react-native-reanimated'
import { ReanimatedScrollEvent } from 'react-native-reanimated/lib/typescript/hook/commonTypes'

export type ScrollDirection = 'to-top' | 'to-bottom' | 'idle'
export type ScrollDirectionValue = SharedValue<ScrollDirection>

export const useScrollDirection = (mode?: 'include-negative') => {
  const direction = useSharedValue<ScrollDirection>('idle')
  const lastOffsetY = useSharedValue(0)
  const dragStartAnchor = useSharedValue(0)
  const directionChangeAnchor = useSharedValue(0)

  const onBeginDrag = (e: ReanimatedScrollEvent | number) => {
    'worklet'
    const y = typeof e === 'number' ? e : e.contentOffset.y
    dragStartAnchor.set(y)
  }

  const onScroll = (e: ReanimatedScrollEvent | number) => {
    'worklet'
    const rawY = typeof e === 'number' ? e : e.contentOffset.y

    const clampedY = mode === 'include-negative' ? rawY : Math.max(rawY, 0)
    const clampedPrev =
      mode === 'include-negative'
        ? lastOffsetY.get()
        : Math.max(lastOffsetY.get(), 0)

    // Detect direction changes
    if (
      clampedPrev - clampedY < 0 &&
      (direction.get() === 'idle' || direction.get() === 'to-top')
    ) {
      direction.set('to-bottom')
      directionChangeAnchor.set(rawY)
    }

    if (
      clampedPrev - clampedY > 0 &&
      (direction.get() === 'idle' || direction.get() === 'to-bottom')
    ) {
      direction.set('to-top')
      directionChangeAnchor.set(rawY)
    }

    lastOffsetY.set(rawY)
  }

  return {
    scrollDirection: direction,
    offsetYAnchorOnBeginDrag: dragStartAnchor,
    offsetYAnchorOnChangeDirection: directionChangeAnchor,
    onBeginDrag,
    onScroll,
  }
}
