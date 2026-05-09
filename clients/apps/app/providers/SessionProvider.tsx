/**
 * Session persistence provider for the Rapidly mobile app.
 *
 * Stores the OAuth access token in secure storage and mirrors it to
 * the Apple Extension Storage so the widget can authenticate API calls.
 */
import { useStorageState } from '@/hooks/storage'
import { ExtensionStorage } from '@bacons/apple-targets'
import {
  createContext,
  useContext,
  useEffect,
  type PropsWithChildren,
} from 'react'

const widgetStorage = new ExtensionStorage('group.com.rapidly-tech.Rapidly')

interface SessionState {
  setSession: (token: string | null) => void
  session?: string | null
  isLoading: boolean
}

const AuthCtx = createContext<SessionState>({
  setSession: () => null,
  session: null,
  isLoading: false,
})

export function useSession() {
  const ctx = useContext(AuthCtx)
  if (process.env.NODE_ENV !== 'production' && !ctx) {
    throw new Error('useSession must be wrapped in a <SessionProvider />')
  }
  return ctx
}

export function SessionProvider({ children }: PropsWithChildren) {
  const [[isLoading, session], setSession] = useStorageState('session')

  // Mirror the token to the widget extension
  useEffect(() => {
    if (session) {
      widgetStorage.set('widget_api_token', session)
    }
  }, [session])

  return (
    <AuthCtx.Provider value={{ setSession, session, isLoading }}>
      {children}
    </AuthCtx.Provider>
  )
}
