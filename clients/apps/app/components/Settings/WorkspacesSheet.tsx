/**
 * Bottom sheet for switching between workspaces.
 *
 * Lists all workspaces the user belongs to with avatars and checkmarks.
 * Includes a "New" button to navigate to the onboarding flow.
 */
import { useTheme } from '@/design-system/useTheme'
import { WorkspaceContext } from '@/providers/WorkspaceProvider'
import { router } from 'expo-router'
import { useContext } from 'react'
import { Iconify } from 'react-native-iconify'
import { Avatar } from '../Shared/Avatar'
import { BottomSheet } from '../Shared/BottomSheet'
import { Box } from '../Shared/Box'
import { Button } from '../Shared/Button'
import { Text } from '../Shared/Text'
import { Touchable } from '../Shared/Touchable'

export interface WorkspacesSheetProps {
  onDismiss: () => void
  onSelect?: () => void
}

export const WorkspacesSheet = ({
  onDismiss,
  onSelect,
}: WorkspacesSheetProps) => {
  const {
    setWorkspace,
    workspace: activeWorkspace,
    workspaces,
  } = useContext(WorkspaceContext)
  const theme = useTheme()

  const handlePick = (ws: (typeof workspaces)[number]) => {
    const switched = activeWorkspace?.id !== ws.id
    setWorkspace(ws)
    onDismiss()
    if (switched) onSelect?.()
  }

  return (
    <BottomSheet
      onDismiss={onDismiss}
      snapPoints={['40%']}
      enableDynamicSizing={false}
    >
      <Box gap="spacing-16">
        {/* Header row */}
        <Box flexDirection="row" justifyContent="space-between">
          <Text variant="title">Workspaces</Text>
          <Button
            size="small"
            onPress={() => router.push('/onboarding')}
            icon={
              <Iconify
                icon="solar:add-circle-linear"
                size={16}
                color={theme.colors.monochrome}
              />
            }
          >
            New
          </Button>
        </Box>

        {/* Workspace list */}
        <Box flexDirection="column">
          {workspaces.map((ws) => {
            const isActive = activeWorkspace?.id === ws.id
            return (
              <Touchable
                key={ws.id}
                style={{
                  paddingVertical: theme.spacing['spacing-12'],
                  paddingLeft: theme.spacing['spacing-16'],
                  paddingRight: theme.spacing['spacing-24'],
                  borderRadius: theme.borderRadii['border-radius-16'],
                  flexDirection: 'row',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: theme.spacing['spacing-12'],
                  backgroundColor: isActive ? theme.colors.card : undefined,
                }}
                onPress={() => handlePick(ws)}
                activeOpacity={0.6}
              >
                <Box flexDirection="row" alignItems="center" gap="spacing-12">
                  <Avatar size={24} image={ws.avatar_url} name={ws.name} />
                  <Text>{ws.name}</Text>
                </Box>
                {isActive ? (
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
