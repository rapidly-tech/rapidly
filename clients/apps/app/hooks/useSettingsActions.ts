/**
 * Business logic for settings-screen destructive actions.
 *
 * Handles the full account deletion flow: iterates through all workspaces,
 * attempts to delete each, then deletes the user account itself. Surfaces
 * support alerts when a workspace has active orders preventing deletion.
 */
import { useLogout } from '@/hooks/auth'
import { useDeleteUser } from '@/hooks/rapidly/users'
import { useDeleteWorkspace } from '@/hooks/rapidly/workspaces'
import { schemas } from '@rapidly-tech/client'
import { useCallback, useState } from 'react'
import { Alert, Linking } from 'react-native'

const SUPPORT_PAGE = 'https://rapidly.tech/docs/support'

interface UseSettingsActionsOptions {
  selectedWorkspace: schemas['Workspace'] | undefined
  workspaces: schemas['Workspace'][]
  setWorkspace: (workspace: schemas['Workspace']) => void
  refetch: () => Promise<unknown>
  userEmail: string | undefined
}

/** Shows a two-button alert directing the user to support. */
function promptForSupport(heading: string, body: string) {
  Alert.alert(heading, body, [
    { text: 'Cancel', style: 'cancel' },
    { text: 'Contact Support', onPress: () => Linking.openURL(SUPPORT_PAGE) },
  ])
}

export const useSettingsActions = ({
  selectedWorkspace,
  workspaces,
  setWorkspace,
  refetch,
}: UseSettingsActionsOptions) => {
  const logout = useLogout()
  const deleteWorkspace = useDeleteWorkspace()
  const deleteUser = useDeleteUser()

  const [isDeletingAccount, setIsDeletingAccount] = useState(false)

  const performDeleteAccount = useCallback(async () => {
    setIsDeletingAccount(true)

    try {
      const failedOrgNames: string[] = []
      const removedOrgIds: string[] = []

      // Phase 1: attempt to delete every workspace
      for (const org of workspaces) {
        const { data, error } = await deleteWorkspace.mutateAsync(org.id)

        if (error || data?.requires_support) {
          failedOrgNames.push(org.name)
        } else if (data?.deleted) {
          removedOrgIds.push(org.id)
        }
      }

      // If some workspaces couldn't be deleted, re-select a valid one and bail
      if (failedOrgNames.length > 0) {
        if (selectedWorkspace && removedOrgIds.includes(selectedWorkspace.id)) {
          const fallback = workspaces.find((o) => !removedOrgIds.includes(o.id))
          if (fallback) setWorkspace(fallback)
        }

        await refetch()
        setIsDeletingAccount(false)

        const names = failedOrgNames.join(', ')
        const plural = failedOrgNames.length > 1 ? 's have' : ' has'
        promptForSupport(
          'Unable to delete account',
          `The following workspace${plural} active orders and cannot be deleted: ${names}. Please contact support for assistance.`,
        )
        return
      }

      // Phase 2: delete the user account
      const { data, error } = await deleteUser.mutateAsync()

      if (error) {
        setIsDeletingAccount(false)
        promptForSupport(
          'Unable to delete account',
          'An unexpected error occurred. Please contact support for assistance.',
        )
        return
      }

      if (data?.deleted) {
        logout()
      } else {
        setIsDeletingAccount(false)
        promptForSupport(
          'Unable to delete account',
          'An unexpected error occurred. Please contact support for assistance.',
        )
      }
    } catch (err) {
      console.error('[Delete Account] Unexpected error:', err)
      setIsDeletingAccount(false)
      promptForSupport(
        'Unable to delete account',
        'An unexpected error occurred. Please contact support for assistance.',
      )
    }
  }, [
    workspaces,
    selectedWorkspace,
    setWorkspace,
    deleteWorkspace,
    deleteUser,
    logout,
    refetch,
  ])

  return { performDeleteAccount, isDeletingAccount, logout }
}
