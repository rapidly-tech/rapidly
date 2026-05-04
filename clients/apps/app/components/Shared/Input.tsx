/**
 * Styled text input that inherits Rapidly theme tokens.
 *
 * Applies card background, border color, rounded corners, and dark
 * keyboard appearance by default.
 */
import { useTheme } from '@/design-system/useTheme'
import { TextInput, TextInputProps } from 'react-native'

export const Input = (props: TextInputProps) => {
  const theme = useTheme()

  const baseStyle = {
    borderRadius: theme.borderRadii['border-radius-12'],
    borderWidth: 1,
    padding: theme.spacing['spacing-16'],
    fontSize: 16,
    backgroundColor: theme.colors.card,
    color: theme.colors.text,
    borderColor: theme.colors.border,
  }

  return (
    <TextInput
      {...props}
      placeholderTextColor={theme.colors.subtext}
      keyboardAppearance="dark"
      style={[baseStyle, props.style]}
    />
  )
}
