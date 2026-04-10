/**
 * Unified pressable wrapper supporting three feedback modes.
 *
 * - "opacity"   (default): fades content on press via TouchableOpacity
 * - "highlight": shows an underlay color via TouchableHighlight
 * - "none":     no visual feedback via TouchableWithoutFeedback
 *
 * All modes trigger haptic feedback on long press when a handler is provided.
 */
import { Theme } from '@/design-system/theme'
import { BoxProps } from '@shopify/restyle'
import * as Haptics from 'expo-haptics'
import { useCallback } from 'react'
import type {
  GestureResponderEvent,
  TouchableWithoutFeedbackProps,
} from 'react-native'
import {
  TouchableHighlight,
  TouchableOpacity,
  TouchableWithoutFeedback,
} from 'react-native'

type FeedbackMode = 'none' | 'highlight' | 'opacity'

interface TouchableProps extends TouchableWithoutFeedbackProps {
  children: React.ReactNode
  feedback?: FeedbackMode
  activeOpacity?: number
  isListItem?: boolean
  boxProps?: BoxProps<Theme>
}

export const Touchable = ({
  feedback = 'opacity',
  onPress,
  onLongPress: rawLongPress,
  isListItem,
  children,
  activeOpacity = 0.6,
  boxProps,
  style,
  ...rest
}: TouchableProps) => {
  // Wrap the long-press handler to add haptic feedback
  const onLongPress = useCallback(
    (event: GestureResponderEvent) => {
      if (rawLongPress) {
        rawLongPress(event)
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy)
      }
    },
    [rawLongPress],
  )

  const pressDelay = isListItem ? 130 : 0

  const sharedProps = {
    onPress,
    onLongPress,
    delayPressIn: pressDelay,
    delayPressOut: pressDelay,
    style,
    ...rest,
  }

  if (feedback === 'highlight') {
    return (
      <TouchableHighlight activeOpacity={activeOpacity} {...sharedProps}>
        {children}
      </TouchableHighlight>
    )
  }

  if (feedback === 'opacity') {
    return (
      <TouchableOpacity activeOpacity={activeOpacity} {...sharedProps}>
        {children}
      </TouchableOpacity>
    )
  }

  return (
    <TouchableWithoutFeedback {...sharedProps}>
      {children}
    </TouchableWithoutFeedback>
  )
}
