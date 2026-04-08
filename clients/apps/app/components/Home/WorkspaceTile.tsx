/**
 * Home dashboard tile displaying the active workspace identity.
 *
 * Shows the workspace avatar, name, and slug. Tapping opens the
 * workspace switcher sheet.
 */
import { Box } from '@/components/Shared/Box'
import { useTheme } from '@/design-system/useTheme'
import { WorkspaceContext } from '@/providers/WorkspaceProvider'
import { useContext } from 'react'
import { Avatar } from '../Shared/Avatar'
import { Text } from '../Shared/Text'
import { Tile } from './Tile'

export interface WorkspaceTileProps {
  onPress: () => void
  loading?: boolean
}

export const WorkspaceTile = ({ onPress, loading }: WorkspaceTileProps) => {
  const { workspace } = useContext(WorkspaceContext)
  const theme = useTheme()

  if (!workspace) return null

  const avatarBg = workspace.avatar_url ? undefined : theme.colors.primary

  return (
    <Tile onPress={onPress}>
      <Box flex={1} flexDirection="column" justifyContent="space-between">
        <Avatar
          name={workspace.name}
          image={workspace.avatar_url}
          backgroundColor={avatarBg}
        />

        <Box flexDirection="column" gap="spacing-4">
          <Text
            variant="subtitle"
            style={{ fontWeight: '600' }}
            loading={loading}
            placeholderText="Workspace"
            placeholderNumberOfLines={2}
          >
            {workspace.name}
          </Text>
          <Text
            variant="body"
            color="subtext"
            numberOfLines={1}
            loading={loading}
            placeholderText="org-slug"
          >
            {workspace.slug}
          </Text>
        </Box>
      </Box>
    </Tile>
  )
}
