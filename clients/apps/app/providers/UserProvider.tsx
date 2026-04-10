/**
 * Authenticated user info provider for the Rapidly mobile app.
 *
 * Fetches the current user's profile from the OAuth2 userinfo endpoint
 * when a session token is available and exposes it via the useUser hook.
 */
import { useSession } from '@/providers/SessionProvider'
import { useQuery } from '@tanstack/react-query'
import { createContext, PropsWithChildren, useContext } from 'react'

export interface User {
  sub: string
  email: string
  name?: string
  picture?: string
}

interface UserState {
  user: User | undefined
  isLoading: boolean
}

const UserCtx = createContext<UserState>({ user: undefined, isLoading: true })

export const useUser = () => useContext(UserCtx)

async function fetchUserInfo(token: string): Promise<User> {
  const res = await fetch(
    `${process.env.EXPO_PUBLIC_RAPIDLY_SERVER_URL}/api/oauth2/userinfo`,
    {
      method: 'GET',
      headers: { Authorization: `Bearer ${token}` },
    },
  )

  if (!res.ok) throw new Error('Failed to fetch user info')
  return res.json()
}

export function UserProvider({ children }: PropsWithChildren) {
  const { session } = useSession()

  const { data: user, isLoading } = useQuery({
    queryKey: ['userinfo'],
    queryFn: () => fetchUserInfo(session!),
    enabled: !!session,
  })

  return (
    <UserCtx.Provider value={{ user, isLoading }}>{children}</UserCtx.Provider>
  )
}
