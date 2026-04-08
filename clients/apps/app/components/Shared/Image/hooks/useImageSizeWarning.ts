/**
 * Development-only hook that flags images whose source resolution
 * is significantly larger or smaller than their rendered size.
 *
 * Thresholds:
 *  - >400 % of the layout pixel size  -> "large" warning
 *  - < 90 % of the layout pixel size  -> "small" warning
 */
import { useCallback, useRef, useState } from 'react'
import { LayoutChangeEvent, PixelRatio } from 'react-native'

const OVERSIZED_THRESHOLD = 400
const UNDERSIZED_THRESHOLD = 90

interface SizeWarning {
  type: 'large' | 'small'
  target: number
  actual: number
}

interface UseImageSizeWarningReturn {
  sizeWarning: SizeWarning | null
  onLayout: (event: LayoutChangeEvent) => void
  onImageLoad: (width: number) => void
}

export const useImageSizeWarning = (): UseImageSizeWarningReturn => {
  const [sizeWarning, setSizeWarning] = useState<SizeWarning | null>(null)

  const renderedWidth = useRef(0)
  const sourceWidth = useRef(0)

  const evaluateSize = useCallback(() => {
    if (!renderedWidth.current || !sourceWidth.current) return

    const expectedPixelWidth = PixelRatio.getPixelSizeForLayoutSize(
      Math.round(renderedWidth.current),
    )
    const ratio = Math.round((sourceWidth.current / expectedPixelWidth) * 100)

    if (ratio > OVERSIZED_THRESHOLD) {
      setSizeWarning({
        type: 'large',
        target: expectedPixelWidth,
        actual: sourceWidth.current,
      })
    } else if (ratio < UNDERSIZED_THRESHOLD) {
      setSizeWarning({
        type: 'small',
        target: expectedPixelWidth,
        actual: sourceWidth.current,
      })
    } else {
      setSizeWarning(null)
    }
  }, [])

  const onLayout = useCallback(
    (event: LayoutChangeEvent) => {
      renderedWidth.current = event.nativeEvent.layout.width
      evaluateSize()
    },
    [evaluateSize],
  )

  const onImageLoad = useCallback(
    (width: number) => {
      sourceWidth.current = width
      evaluateSize()
    },
    [evaluateSize],
  )

  return { sizeWarning, onLayout, onImageLoad }
}
