/**
 * Generic bottom sheet for picking a value from a list.
 *
 * Renders a title, optional description, and a vertical list of tappable
 * options. The currently selected value is highlighted with a checkmark.
 */
import { useTheme } from '@/design-system/useTheme'
import { BottomSheetProps as GorhomSheetProps } from '@gorhom/bottom-sheet'
import { Iconify } from 'react-native-iconify'
import { BottomSheet } from '../Shared/BottomSheet'
import { Box } from '../Shared/Box'
import { Text } from '../Shared/Text'
import { Touchable } from '../Shared/Touchable'

interface SelectionItem<T> {
  value: T
  label: string
}

export interface SelectionSheetProps<T> {
  onDismiss?: () => void
  onSelect: (value: T) => void
  title: string
  description?: string
  items: SelectionItem<T>[]
  selectedValue?: T
  snapPoints?: GorhomSheetProps['snapPoints']
}

export const SelectionSheet = <T,>({
  onDismiss,
  onSelect,
  title,
  items,
  selectedValue,
  description,
  snapPoints = ['40%'],
}: SelectionSheetProps<T>) => {
  const theme = useTheme()

  return (
    <BottomSheet
      onDismiss={onDismiss}
      snapPoints={snapPoints}
      enableDynamicSizing={true}
    >
      <Box gap="spacing-24">
        {/* Header */}
        <Box flexDirection="column" gap="spacing-8">
          <Text variant="title">{title}</Text>
          {description ? (
            <Text variant="bodySmall" color="subtext">
              {description}
            </Text>
          ) : null}
        </Box>

        {/* Option list */}
        <Box flexDirection="column">
          {items.map((item) => {
            const isSelected = selectedValue === item.value

            return (
              <Touchable
                key={item.label}
                style={{
                  paddingVertical: theme.spacing['spacing-12'],
                  paddingLeft: theme.spacing['spacing-16'],
                  paddingRight: theme.spacing['spacing-24'],
                  borderRadius: theme.borderRadii['border-radius-16'],
                  flexDirection: 'row',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: theme.spacing['spacing-12'],
                  backgroundColor: isSelected ? theme.colors.card : undefined,
                }}
                onPress={() => onSelect(item.value)}
                activeOpacity={0.6}
              >
                <Box flexDirection="row" alignItems="center" gap="spacing-12">
                  <Text>{item.label}</Text>
                </Box>
                {isSelected ? (
                  <Iconify
                    icon="solar:check-read-linear"
                    size={20}
                    color={theme.colors.monochromeInverted}
                  />
                ) : null}
              </Touchable>
            )
          })}
        </Box>
      </Box>
    </BottomSheet>
  )
}
