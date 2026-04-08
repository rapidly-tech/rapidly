/**
 * Themed toggle switch that maps to the platform's native Switch control.
 */
import { useTheme } from '@/design-system/useTheme'
import { Switch as NativeSwitch } from 'react-native'

export interface SwitchProps {
  value: boolean
  onValueChange: (nextValue: boolean) => void
  disabled?: boolean
}

export const Switch = ({ value, onValueChange, disabled }: SwitchProps) => {
  const theme = useTheme()

  return (
    <NativeSwitch
      value={value}
      onValueChange={onValueChange}
      disabled={disabled}
      trackColor={{
        false: theme.colors.border,
        true: theme.colors.primary,
      }}
      thumbColor={theme.colors.monochromeInverted}
      ios_backgroundColor={theme.colors.border}
    />
  )
}
