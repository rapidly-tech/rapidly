/**
 * react-hook-form controlled text input with optional label.
 *
 * Wraps the shared Input component and wires it to the form controller.
 * When a `label` is provided the input is rendered inside a vertical
 * layout with label + optional secondary label above it.
 */
import { Box } from '@/components/Shared/Box'
import { Input } from '@/components/Shared/Input'
import { useTheme } from '@/design-system/useTheme'
import {
  Control,
  FieldValues,
  useController,
  UseControllerProps,
} from 'react-hook-form'
import { TextInputProps } from 'react-native'
import { Text } from '../Shared/Text'

export type FormInputProps<T extends FieldValues> = TextInputProps & {
  control: Control<T>
  name: UseControllerProps<T>['name']
  defaultValue?: UseControllerProps<T>['defaultValue']
  label?: string
  secondaryLabel?: string
}

export const FormInput = <T extends FieldValues>({
  control,
  name,
  defaultValue,
  label,
  secondaryLabel,
  ...inputProps
}: FormInputProps<T>) => {
  const { field } = useController({ control, name, defaultValue })
  const theme = useTheme()

  // Labelled variant
  if (label) {
    return (
      <Box flexDirection="column" gap="spacing-8">
        <Box flexDirection="row" gap="spacing-8" justifyContent="space-between">
          <Text color="subtext">{label}</Text>
          {secondaryLabel ? (
            <Text color="subtext">{secondaryLabel}</Text>
          ) : null}
        </Box>
        <Input
          value={field.value}
          onChangeText={field.onChange}
          {...inputProps}
        />
      </Box>
    )
  }

  // Bare input (no label)
  return (
    <Input
      value={field.value}
      onChangeText={field.onChange}
      placeholderTextColor={theme.colors.subtext}
      {...inputProps}
    />
  )
}
