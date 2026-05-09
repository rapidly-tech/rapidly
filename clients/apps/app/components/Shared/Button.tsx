/**
 * Multi-variant pressable button with loading and icon support.
 *
 * Resolves its visual style from the design-system button variants, applies
 * the selected size configuration, and handles disabled/loading states.
 */
import { ActivityIndicator } from 'react-native'

import { Text } from '@/components/Shared/Text'
import {
  ButtonVariantKey,
  buttonVariants,
} from '@/design-system/buttonVariants'
import { TextVariantKey } from '@/design-system/textVariants'
import { DimensionToken, SpacingToken } from '@/design-system/theme'
import { useTheme } from '@/design-system/useTheme'
import { Box } from './Box'
import { Touchable } from './Touchable'

export type ButtonSize = 'small' | 'medium'

interface SizeSpec {
  height?: DimensionToken
  px: SpacingToken
  py: SpacingToken
  labelVariant: TextVariantKey
}

const SIZE_MAP: Record<ButtonSize, SizeSpec> = {
  small: {
    px: 'spacing-12',
    py: 'spacing-6',
    labelVariant: 'bodySmall',
  },
  medium: {
    height: 'dimension-50',
    px: 'spacing-16',
    py: 'spacing-10',
    labelVariant: 'bodyMedium',
  },
}

export type ButtonProps = {
  onPress?: () => void
  children: React.ReactNode
  variant?: ButtonVariantKey
  size?: ButtonSize
  disabled?: boolean
  loading?: boolean
  fullWidth?: boolean
  icon?: React.ReactNode
}

export const Button = ({
  onPress,
  children,
  variant = 'primary',
  size = 'medium',
  disabled = false,
  loading = false,
  fullWidth = false,
  icon,
}: ButtonProps) => {
  const theme = useTheme()
  const variantTokens = buttonVariants[variant]
  const sizeSpec = SIZE_MAP[size]

  const bgToken = disabled
    ? variantTokens.disabledBackgroundColor
    : variantTokens.backgroundColor

  const fgToken = disabled
    ? variantTokens.disabledTextColor
    : variantTokens.textColor

  const isInteractive = !disabled && !loading

  return (
    <Touchable onPress={onPress} disabled={!isInteractive}>
      <Box
        paddingHorizontal={sizeSpec.px}
        paddingVertical={sizeSpec.py}
        borderRadius="border-radius-999"
        flexDirection="row"
        alignItems="center"
        justifyContent="center"
        style={
          sizeSpec.height
            ? { height: theme.dimension[sizeSpec.height] }
            : undefined
        }
        opacity={disabled ? 0.7 : 1}
        backgroundColor={bgToken}
        width={fullWidth ? '100%' : undefined}
      >
        {loading ? (
          <Box marginRight="spacing-8">
            <ActivityIndicator size="small" color={theme.colors[fgToken]} />
          </Box>
        ) : null}

        {icon && !loading ? <Box marginRight="spacing-4">{icon}</Box> : null}

        <Text variant={sizeSpec.labelVariant} color={fgToken}>
          {children}
        </Text>
      </Box>
    </Touchable>
  )
}
