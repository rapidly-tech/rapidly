/**
 * Card container for key-value detail rows.
 *
 * `Details` provides the styled wrapper; `DetailRow` renders a single
 * label + value pair in a horizontal layout with an em-dash fallback
 * when no value is provided.
 */
import { Box } from '@/components/Shared/Box'
import { StyleProp, TextStyle, ViewStyle } from 'react-native'
import { Text } from './Text'

export const Details = ({
  children,
  style,
}: {
  children: React.ReactNode
  style?: StyleProp<ViewStyle>
}) => (
  <Box
    backgroundColor="card"
    padding="spacing-16"
    borderRadius="border-radius-12"
    gap="spacing-8"
    style={style}
  >
    {children}
  </Box>
)

export const DetailRow = ({
  label,
  labelStyle,
  value,
  valueStyle,
}: {
  label: string
  labelStyle?: StyleProp<TextStyle>
  value?: React.ReactNode
  valueStyle?: StyleProp<TextStyle>
}) => {
  const hasValue = value !== undefined && value !== null

  return (
    <Box flexDirection="row" justifyContent="space-between" gap="spacing-8">
      <Text color="subtext" style={labelStyle}>
        {label}
      </Text>
      <Text
        numberOfLines={1}
        ellipsizeMode="tail"
        color={hasValue ? 'text' : 'subtext'}
        textAlign="right"
        style={valueStyle}
      >
        {hasValue ? value : '\u2014'}
      </Text>
    </Box>
  )
}
