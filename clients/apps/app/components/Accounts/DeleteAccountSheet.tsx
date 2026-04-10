/**
 * Confirmation sheet for permanent account deletion.
 *
 * The user must type their email to confirm the destructive action.
 * Disables the delete button until the entered email matches the
 * authenticated user's email.
 */
import { Button } from '@/components/Shared/Button'
import { Text } from '@/components/Shared/Text'
import { useTheme } from '@/design-system/useTheme'
import { useWorkspaces } from '@/hooks/rapidly/workspaces'
import { useSettingsActions } from '@/hooks/useSettingsActions'
import { useUser } from '@/providers/UserProvider'
import { WorkspaceContext } from '@/providers/WorkspaceProvider'
import { BottomSheetTextInput } from '@gorhom/bottom-sheet'
import React, { useContext, useState } from 'react'
import { BottomSheet } from '../Shared/BottomSheet'

export interface DeleteAccountSheetProps {
  onDismiss: () => void
}

export const DeleteAccountSheet = ({ onDismiss }: DeleteAccountSheetProps) => {
  const theme = useTheme()
  const [confirmationEmail, setConfirmationEmail] = useState('')

  const {
    setWorkspace,
    workspace: activeWorkspace,
    workspaces,
  } = useContext(WorkspaceContext)
  const { refetch } = useWorkspaces()
  const { user } = useUser()

  const { performDeleteAccount, isDeletingAccount } = useSettingsActions({
    selectedWorkspace: activeWorkspace,
    workspaces,
    setWorkspace,
    refetch,
    userEmail: user?.email,
  })

  const emailMatches = confirmationEmail === user?.email
  const canDelete = emailMatches && !isDeletingAccount

  return (
    <BottomSheet onDismiss={onDismiss}>
      <Text variant="title">Delete Account</Text>
      <Text color="subtext">
        Deleting your workspaces & account is an irreversible action.
      </Text>
      <Text color="subtext">Enter your email below to confirm.</Text>

      <BottomSheetTextInput
        style={{
          backgroundColor: theme.colors.inputBackground,
          borderRadius: theme.borderRadii['border-radius-12'],
          paddingHorizontal: theme.spacing['spacing-12'],
          paddingVertical: theme.spacing['spacing-10'],
          marginVertical: theme.spacing['spacing-12'],
          fontSize: 16,
          color: theme.colors.monochromeInverted,
        }}
        placeholderTextColor={theme.colors.inputPlaceholder}
        placeholder={user?.email}
        onChangeText={setConfirmationEmail}
        value={confirmationEmail}
      />

      <Button
        disabled={!canDelete}
        loading={isDeletingAccount}
        variant="destructive"
        onPress={performDeleteAccount}
      >
        Delete Account
      </Button>
    </BottomSheet>
  )
}
