/**
 * Provider that initialises and distributes the Rapidly API client.
 *
 * Re-creates the client instance whenever the session token changes
 * so that all downstream hooks authenticate with the current token.
 */
import { Client, initApiClient } from '@rapidly-tech/client'
import { createContext, useContext, type PropsWithChildren } from 'react'
import { useSession } from './SessionProvider'

const DEFAULT_BASE =
  process.env.EXPO_PUBLIC_RAPIDLY_SERVER_URL ?? 'https://api.rapidly.tech'

const RapidlyClientCtx = createContext<{ rapidly: Client }>({
  rapidly: initApiClient(DEFAULT_BASE),
})

export function useRapidlyClient() {
  const ctx = useContext(RapidlyClientCtx)
  if (process.env.NODE_ENV !== 'production' && !ctx) {
    throw new Error(
      'useRapidlyClient must be wrapped in a <RapidlyClientProvider />',
    )
  }
  return ctx
}

export function RapidlyClientProvider({ children }: PropsWithChildren) {
  const { session } = useSession()

  const client = initApiClient(DEFAULT_BASE, session ?? '')

  return (
    <RapidlyClientCtx.Provider value={{ rapidly: client }}>
      {children}
    </RapidlyClientCtx.Provider>
  )
}
