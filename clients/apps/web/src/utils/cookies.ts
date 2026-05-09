import { schemas } from '@rapidly-tech/client'
import { ReadonlyRequestCookies } from 'next/dist/server/web/spec-extension/adapters/request-cookies'

const COOKIE_NAME = 'last_visited_org'
const THIRTY_DAYS_IN_SECONDS = 30 * 24 * 60 * 60

/**
 * Persists the most recently visited workspace slug as a secure cookie
 * so the app can redirect back to it on the next visit.
 */
export const setLastVisitedOrg = (
  workspace: string,
  maxAge: number = THIRTY_DAYS_IN_SECONDS,
) => {
  const flags = `max-age=${maxAge}; path=/; SameSite=Lax; Secure`
  document.cookie = `${COOKIE_NAME}=${workspace}; ${flags}`
}

/**
 * Reads the last-visited workspace slug from server-side cookies and
 * resolves it against the user's workspace list. Returns `undefined`
 * when the cookie is absent or refers to a workspace the user can no
 * longer access.
 */
export const getLastVisitedOrg = (
  cookies: ReadonlyRequestCookies,
  workspaces: schemas['Workspace'][],
): schemas['Workspace'] | undefined => {
  const slug = cookies.get(COOKIE_NAME)?.value
  if (!slug) return undefined
  return workspaces.find((ws) => ws.slug === slug)
}
