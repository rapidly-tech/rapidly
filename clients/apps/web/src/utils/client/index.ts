import { toast } from '@/components/Toast/use-toast'
import {
  initApiClient as baseCreateClient,
  Client,
  Middleware,
} from '@rapidly-tech/client'
import { ReadonlyRequestCookies } from 'next/dist/server/web/spec-extension/adapters/request-cookies'
import { NextRequest } from 'next/server'

/**
 * Middleware that surfaces network-level failures (connection refused,
 * timeout, DNS errors) as a user-facing toast.
 */
const networkErrorHandler: Middleware = {
  onError: async () => {
    toast({
      title: 'A network error occurred',
      description: 'Please try again later',
    })
  },
}

/**
 * Creates a browser-side API client. An optional bearer token can be
 * supplied for customer-portal sessions that authenticate via JWT.
 */
export const buildClientAPI = (token?: string): Client => {
  const instance = baseCreateClient(
    process.env.NEXT_PUBLIC_API_URL as string,
    token,
  )
  instance.use(networkErrorHandler)
  return instance
}

// Default singleton used by client-side hooks and components.
export const api = buildClientAPI()

/**
 * Creates a server-side API client that forwards the incoming request's
 * cookies and selected headers to the backend.
 *
 * Uses `RAPIDLY_API_URL` when available (e.g. inside Docker) and falls
 * back to `NEXT_PUBLIC_API_URL` for local development.
 */
export const buildServerAPI = async (
  reqHeaders: NextRequest['headers'],
  reqCookies: ReadonlyRequestCookies,
  token?: string,
): Promise<Client> => {
  const extra: Record<string, string> = {}

  // Forward the real client IP when behind a reverse proxy.
  const forwardedFor = reqHeaders.get('X-Forwarded-For')
  if (forwardedFor) {
    extra['X-Forwarded-For'] = forwardedFor
  }

  // Relay session cookies so the backend sees the user's auth state.
  extra['Cookie'] = reqCookies.toString()

  // GitHub Codespaces requires a token for forwarded-port access.
  const ghToken = process.env.GITHUB_TOKEN
  if (ghToken) {
    extra['X-Github-Token'] = ghToken
  }

  const baseUrl =
    process.env.RAPIDLY_API_URL ?? (process.env.NEXT_PUBLIC_API_URL as string)

  return baseCreateClient(baseUrl, token, extra)
}
