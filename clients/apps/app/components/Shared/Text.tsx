/**
 * Theme-aware text component with built-in skeleton support.
 *
 * Renders text using the Restyle variant system. When `loading` is true the
 * component shows a shimmer placeholder sized to match the selected variant's
 * font metrics, supporting both single-line and multi-line skeletons.
 */
import { TextVariantKey, textVariants } from '@/design-system/textVariants'
import { BorderRadiiToken, ColorToken, Theme } from '@/design-system/theme'
import { createText, TextProps } from '@shopify/restyle'
import { Text as RNText } from 'react-native'
import { Box } from './Box'
import { PlaceholderBox } from './PlaceholderBox'

const RestyleText = createText<Theme>()

type Props = TextProps<Theme> &
  React.ComponentProps<typeof RNText> & {
    variant?: TextVariantKey
    loading?: boolean
    placeholderText?: string
    placeholderNumberOfLines?: number
    placeholderColor?: ColorToken
    borderRadius?: BorderRadiiToken
  }

/** Resolves font metrics for a given variant, falling back to defaults. */
function metricsForVariant(variant: TextVariantKey) {
  const style = textVariants[variant] ?? textVariants.defaults
  const fontSize = style.fontSize ?? textVariants.defaults.fontSize ?? 16
  const lineHeight = style.lineHeight ?? textVariants.defaults.lineHeight ?? 22
  return { fontSize, lineHeight }
}

export const Text = ({
  variant = 'body',
  loading,
  placeholderText,
  placeholderNumberOfLines = 1,
  placeholderColor,
  borderRadius = 'border-radius-6',
  ...rest
}: Props) => {
  if (!loading) {
    return <RestyleText variant={variant} {...rest} />
  }

  const { fontSize, lineHeight } = metricsForVariant(variant)
  const lineGap = lineHeight - fontSize

  // Multi-line skeleton
  if (placeholderNumberOfLines > 1) {
    return (
      <Box style={{ gap: lineGap }}>
        {Array.from({ length: placeholderNumberOfLines }).map((_, idx) => (
          <PlaceholderBox
            key={idx}
            height={fontSize}
            borderRadius={borderRadius}
            width={idx === placeholderNumberOfLines - 1 ? '60%' : '100%'}
            color={placeholderColor}
          />
        ))}
      </Box>
    )
  }

  // Single-line skeleton: invisible text to preserve layout width
  return (
    <Box position="relative" justifyContent="center">
      <RestyleText
        variant={variant}
        {...rest}
        style={[rest.style, { opacity: 0 }]}
      >
        {placeholderText ?? 'Loading...'}
      </RestyleText>
      <PlaceholderBox
        height={fontSize}
        borderRadius={borderRadius}
        style={{ position: 'absolute', left: 0, right: 0 }}
        color={placeholderColor}
      />
    </Box>
  )
}
