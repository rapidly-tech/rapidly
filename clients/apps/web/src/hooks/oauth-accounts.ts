import { api } from '@/utils/client'
import { schemas } from '@rapidly-tech/client'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useMemo } from 'react'
import { useAuth } from '.'

type OAuthAccount = schemas['OAuthAccountRead']
type Platform = schemas['OAuthPlatform']

// Convenience accessors for the current user's linked OAuth accounts.

export const useOAuthAccounts = (): OAuthAccount[] => {
  const { currentUser } = useAuth()
  return currentUser?.oauth_accounts ?? []
}

export const usePlatformOAuthAccount = (
  platform: Platform,
): OAuthAccount | undefined => {
  const accounts = useOAuthAccounts()
  return useMemo(
    () => accounts.find((a) => a.platform === platform),
    [accounts, platform],
  )
}

export const useMicrosoftAccount = (): OAuthAccount | undefined =>
  usePlatformOAuthAccount('microsoft')

export const useGoogleAccount = (): OAuthAccount | undefined =>
  usePlatformOAuthAccount('google')

/**
 * Mutation hook that unlinks an OAuth provider from the signed-in user.
 * After a successful disconnect the user record and related query caches
 * are refreshed so the UI reflects the change immediately.
 */
export const useDisconnectOAuthAccount = () => {
  const qc = useQueryClient()
  const { reloadUser } = useAuth()

  return useMutation({
    mutationFn: (platform: Platform) =>
      api.DELETE('/api/users/me/oauth-accounts/{platform}', {
        params: { path: { platform } },
      }),
    onSuccess: async () => {
      await reloadUser()
      qc.invalidateQueries({ queryKey: ['user'] })
    },
  })
}
