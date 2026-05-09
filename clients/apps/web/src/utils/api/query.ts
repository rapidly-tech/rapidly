/**
 * Singleton TanStack Query client shared between server and browser.
 *
 * On the server a fresh client is created per request to avoid leaking data
 * across requests.  In the browser we reuse a single instance so React
 * suspense boundaries don't accidentally discard cached data.
 */
export { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { isServer, QueryClient } from '@tanstack/react-query'

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000,
      },
    },
  })
}

let browserQueryClient: QueryClient | undefined = undefined

export function getQueryClient() {
  if (isServer) {
    return makeQueryClient()
  }

  if (!browserQueryClient) {
    browserQueryClient = makeQueryClient()
  }
  return browserQueryClient
}
