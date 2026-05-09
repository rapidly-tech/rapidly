/**
 * Computes header layout dimensions for the home screen.
 *
 * Returns the safe-area inset at the top, the net header height (content
 * area only), and the gross height (content + safe area).
 */
import { useSafeAreaInsets } from 'react-native-safe-area-context'

const HEADER_CONTENT_HEIGHT = 50

export const useHomeHeaderHeight = () => {
  const insets = useSafeAreaInsets()

  const topInset = insets.top
  const grossHeight = HEADER_CONTENT_HEIGHT + topInset

  return {
    topSafeAreaHeight: topInset,
    netHeaderHeight: HEADER_CONTENT_HEIGHT,
    grossHeaderHeight: grossHeight,
  }
}
