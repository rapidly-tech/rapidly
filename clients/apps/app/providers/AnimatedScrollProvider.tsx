/**
 * Shared animated scroll state for the Rapidly home feed.
 *
 * Tracks scroll position, direction, and drag velocity using Reanimated
 * shared values. Coordinates header collapse/expand animations and
 * snap-to-boundary behavior when the user ends a drag mid-transition.
 */
import { useHomeHeaderHeight } from '@/hooks/useHomeHeaderHeight'
import { ScrollDirection, useScrollDirection } from '@/hooks/useScrollDirection'
import {
  createContext,
  FC,
  PropsWithChildren,
  RefObject,
  useContext,
  useRef,
} from 'react'
import Animated, {
  DerivedValue,
  ScrollHandlerProcessed,
  SharedValue,
  useAnimatedScrollHandler,
  useDerivedValue,
  useSharedValue,
} from 'react-native-reanimated'
import { scheduleOnRN } from 'react-native-worklets'

type AnimatedScrollRef = Animated.ScrollView

interface ScrollContextShape {
  headerTop: SharedValue<number>
  isHeaderVisible: DerivedValue<boolean>
  scrollViewRef: RefObject<AnimatedScrollRef | null>
  listPointerEvents: SharedValue<boolean>
  offsetY: SharedValue<number>
  velocityOnEndDrag: SharedValue<number>
  scrollHandler: ScrollHandlerProcessed<Record<string, unknown>>
  scrollDirection: SharedValue<ScrollDirection>
  offsetYAnchorOnBeginDrag: SharedValue<number>
}

const Ctx = createContext<ScrollContextShape>({} as ScrollContextShape)

export const AnimatedScrollProvider: FC<PropsWithChildren> = ({ children }) => {
  const { netHeaderHeight } = useHomeHeaderHeight()

  const svRef = useRef<AnimatedScrollRef | null>(null)
  const pointerEnabled = useSharedValue(true)

  const headerTop = useSharedValue(0)
  const isHeaderVisible = useDerivedValue(
    () =>
      Math.abs(headerTop.get()) >= 0 &&
      Math.abs(headerTop.get()) < netHeaderHeight,
  )

  const offsetY = useSharedValue(0)
  const endDragVelocity = useSharedValue(0)

  // Snap the scroll position after a mid-header drag
  const snapScroll = (targetY: number) => {
    svRef.current?.scrollTo({ y: targetY, animated: true })
    setTimeout(() => pointerEnabled.set(true), 300)
  }

  const {
    onBeginDrag: dirBeginDrag,
    onScroll: dirScroll,
    scrollDirection,
    offsetYAnchorOnBeginDrag,
  } = useScrollDirection()

  const scrollHandler = useAnimatedScrollHandler({
    onBeginDrag: (e) => {
      endDragVelocity.set(0)
      dirBeginDrag(e)
    },
    onScroll: (e) => {
      offsetY.set(e.contentOffset.y)
      dirScroll(e)
    },
    onEndDrag: (e) => {
      endDragVelocity.set(e.velocity?.y ?? 0)

      const absTop = Math.abs(headerTop.get())
      const inTransition = absTop >= 2 && absTop < netHeaderHeight - 2

      if (scrollDirection.get() === 'to-bottom' && inTransition) {
        const target = e.contentOffset.y + (netHeaderHeight - absTop + 2)
        pointerEnabled.set(false)
        scheduleOnRN(snapScroll, target)
      }

      if (scrollDirection.get() === 'to-top' && inTransition) {
        const target = e.contentOffset.y - netHeaderHeight - 2
        pointerEnabled.set(false)
        scheduleOnRN(snapScroll, target)
      }
    },
  })

  const value: ScrollContextShape = {
    headerTop,
    isHeaderVisible,
    scrollViewRef: svRef,
    listPointerEvents: pointerEnabled,
    offsetY,
    velocityOnEndDrag: endDragVelocity,
    scrollHandler,
    scrollDirection,
    offsetYAnchorOnBeginDrag,
  }

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export const useAnimatedScroll = () => {
  const ctx = useContext(Ctx)
  if (!ctx) {
    throw new Error(
      'useAnimatedScroll must be used within an AnimatedScrollProvider',
    )
  }
  return ctx
}
