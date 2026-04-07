/**
 * Deep link routing provider for the Rapidly mobile app.
 *
 * Maintains a registry of path-based handlers. Screens register themselves
 * via the useDeepLinks hook and are unregistered on unmount. Handles
 * both cold-start URLs and runtime deep link events.
 */
import * as Linking from 'expo-linking'
import { useRouter } from 'expo-router'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
} from 'react'

type LinkHandler = (url: URL) => boolean | void

interface DeepLinkAPI {
  registerHandler: (path: string, handler: LinkHandler) => () => void
}

const DeepLinkCtx = createContext<DeepLinkAPI>({
  registerHandler: () => () => {},
})

export const useDeepLinks = () => useContext(DeepLinkCtx)

export default function DeepLinkProvider({
  children,
}: {
  children: React.ReactNode
}) {
  const router = useRouter()
  const registry = useRef<Map<string, LinkHandler>>(new Map())
  const coldStartHandled = useRef(false)

  const registerHandler = useCallback((path: string, handler: LinkHandler) => {
    registry.current.set(path, handler)
    return () => {
      registry.current.delete(path)
    }
  }, [])

  const processLink = useCallback((event: { url: string }) => {
    try {
      const parsed = new URL(event.url)
      const handler = registry.current.get(parsed.hostname)
      if (handler) {
        const consumed = handler(parsed)
        if (consumed !== false) return
      }
    } catch (err) {
      console.error('Error handling deep link:', err)
    }
  }, [])

  useEffect(() => {
    const sub = Linking.addEventListener('url', processLink)

    if (!coldStartHandled.current) {
      Linking.getInitialURL().then((url) => {
        if (url && !coldStartHandled.current) {
          coldStartHandled.current = true
          processLink({ url })
        }
      })
    }

    return () => sub.remove()
  }, [processLink])

  return (
    <DeepLinkCtx.Provider value={{ registerHandler }}>
      {children}
    </DeepLinkCtx.Provider>
  )
}
