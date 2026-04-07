/**
 * Expo Image wrapper with a dev-mode size mismatch overlay.
 *
 * In development builds the component checks whether the loaded source
 * dimensions are wildly different from the rendered layout and overlays
 * a red warning message when they are.
 */
import { Box } from '@/components/Shared/Box'
import { Image as ExpoImage, ImageLoadEventData, ImageProps } from 'expo-image'
import { LayoutChangeEvent, StyleSheet } from 'react-native'
import { Text } from '../Text'
import { useImageSizeWarning } from './hooks/useImageSizeWarning'

export const Image = ({ onLoad, onLayout, style, ...rest }: ImageProps) => {
  const {
    sizeWarning,
    onLayout: warningOnLayout,
    onImageLoad: warningOnLoad,
  } = useImageSizeWarning()

  const handleLoad = (event: ImageLoadEventData) => {
    warningOnLoad(event.source.width)
    onLoad?.(event)
  }

  const handleLayout = (event: LayoutChangeEvent) => {
    warningOnLayout(event)
    onLayout?.(event)
  }

  const shouldShowOverlay = __DEV__ && sizeWarning

  const warningLabel =
    sizeWarning?.type === 'large'
      ? `${Math.round((sizeWarning.actual / sizeWarning.target) * 100) - 100}% too large`
      : sizeWarning
        ? `${100 - Math.round((sizeWarning.actual / sizeWarning.target) * 100)}% too small`
        : ''

  return (
    <>
      <ExpoImage
        {...rest}
        style={style}
        onLayout={handleLayout}
        onLoad={handleLoad}
      />
      {shouldShowOverlay ? (
        <Box
          position="absolute"
          backgroundColor="error"
          justifyContent="center"
          alignItems="center"
          opacity={0.8}
          style={{ ...StyleSheet.absoluteFillObject, zIndex: 999999 }}
        >
          <Text textAlign="center" style={{ fontSize: 9, lineHeight: 10 }}>
            Image is {warningLabel}
          </Text>
        </Box>
      ) : null}
    </>
  )
}

export type { ImageProps }
