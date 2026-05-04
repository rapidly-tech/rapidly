import { usePostHog } from '@/hooks/posthog'
import { AuthContext } from '@/providers/auth'
import { api } from '@/utils/client'
import { resolveResponse, schemas } from '@rapidly-tech/client'
import * as Sentry from '@sentry/nextjs'
import { useCallback, useContext, useEffect } from 'react'

interface AuthState {
  authenticated: boolean
  currentUser: schemas['UserRead'] | undefined
  reloadUser: () => Promise<undefined>
  userWorkspaces: schemas['Workspace'][]
  setWorkspaceMemberships: React.Dispatch<
    React.SetStateAction<schemas['Workspace'][]>
  >
}

const setSentryUser = (user: schemas['UserRead'] | undefined): void => {
  if (user) {
    Sentry.setUser({ id: user.id, email: user.email })
  } else {
    Sentry.setUser(null)
  }
}

export const useAuth = (): AuthState => {
  const posthog = usePostHog()
  const {
    user: currentUser,
    setUser: setCurrentUser,
    userWorkspaces,
    setWorkspaceMemberships,
  } = useContext(AuthContext)

  const reloadUser = useCallback(async (): Promise<undefined> => {
    const user = await resolveResponse(api.GET('/api/users/me'))
    setCurrentUser(user)
  }, [setCurrentUser])

  useEffect(() => {
    setSentryUser(currentUser)

    if (currentUser) {
      posthog.identify(currentUser)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentUser])

  return {
    currentUser,
    authenticated: currentUser !== undefined,
    reloadUser,
    userWorkspaces,
    setWorkspaceMemberships,
  }
}
