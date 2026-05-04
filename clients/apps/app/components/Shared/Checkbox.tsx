/**
 * Circular radio-style checkbox with a text label.
 *
 * Renders a filled inner circle when checked; otherwise an empty ring.
 * The label color shifts between primary and subdued text to visually
 * reinforce the selected state.
 */
import { Box } from '@/components/Shared/Box'
import { useTheme } from '@/design-system/useTheme'
import { Text } from './Text'
import { Touchable } from './Touchable'

export interface CheckboxProps {
  label: string
  checked: boolean
  onChange: (nextValue: boolean) => void
}

export const Checkbox = ({ label, checked, onChange }: CheckboxProps) => {
  const theme = useTheme()

  const handleToggle = () => onChange(!checked)

  return (
    <Touchable
      onPress={handleToggle}
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: theme.spacing['spacing-8'],
      }}
      activeOpacity={0.6}
    >
      <Box
        width={20}
        height={20}
        borderRadius="border-radius-full"
        alignItems="center"
        justifyContent="center"
        borderWidth={1}
        borderColor="border"
      >
        {checked ? (
          <Box
            width={12}
            height={12}
            borderRadius="border-radius-full"
            backgroundColor="monochromeInverted"
          />
        ) : null}
      </Box>

      <Text color={checked ? 'text' : 'subtext'}>{label}</Text>
    </Touchable>
  )
}
