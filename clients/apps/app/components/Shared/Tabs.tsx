/**
 * Lightweight tabs component backed by React context.
 *
 * Composed of four parts:
 *  - Tabs: root controller that holds the active value
 *  - TabsList: horizontal row container for triggers
 *  - TabsTrigger: individual tab button
 *  - TabsContent: content pane that renders only when its value matches
 */
import { Box } from '@/components/Shared/Box'
import { useTheme } from '@/design-system/useTheme'
import {
  createContext,
  PropsWithChildren,
  useCallback,
  useContext,
  useState,
} from 'react'
import { StyleProp, ViewStyle } from 'react-native'
import { Text } from './Text'
import { Touchable } from './Touchable'

interface TabsState {
  activeValue: string
  setActiveValue: (value: string) => void
}

const TabsContext = createContext<TabsState>({
  activeValue: '',
  setActiveValue: () => {},
})

// -- Root --------------------------------------------------------------------

export const Tabs = ({
  defaultValue,
  onValueChange,
  children,
}: {
  defaultValue: string
  onValueChange?: (value: string) => void
  children: React.ReactNode
}) => {
  const [activeValue, setRawValue] = useState(defaultValue)

  const setActiveValue = useCallback(
    (next: string) => {
      setRawValue(next)
      onValueChange?.(next)
    },
    [onValueChange],
  )

  return (
    <TabsContext.Provider value={{ activeValue, setActiveValue }}>
      {children}
    </TabsContext.Provider>
  )
}

// -- Content -----------------------------------------------------------------

export const TabsContent = ({
  children,
  style,
  value,
}: {
  children: React.ReactNode
  style?: StyleProp<ViewStyle>
  value: string
}) => {
  const { activeValue } = useContext(TabsContext)
  if (activeValue !== value) return null
  return <Box style={style}>{children}</Box>
}

// -- List --------------------------------------------------------------------

export const TabsList = ({ children }: PropsWithChildren) => (
  <Box flexDirection="row" gap="spacing-8" alignSelf="flex-start">
    {children}
  </Box>
)

// -- Trigger -----------------------------------------------------------------

export interface TabsTriggerProps {
  value: string
  children: React.ReactNode
}

export const TabsTrigger = ({ value, children }: TabsTriggerProps) => {
  const theme = useTheme()
  const { activeValue, setActiveValue } = useContext(TabsContext)
  const isActive = activeValue === value

  return (
    <Touchable
      style={[
        {
          paddingVertical: theme.dimension['dimension-8'],
          paddingHorizontal: theme.dimension['dimension-16'],
          borderRadius: theme.borderRadii['border-radius-full'],
        },
        isActive && { backgroundColor: theme.colors.card },
      ]}
      onPress={() => setActiveValue(value)}
    >
      <Text color={isActive ? 'text' : 'subtext'}>{children}</Text>
    </Touchable>
  )
}
