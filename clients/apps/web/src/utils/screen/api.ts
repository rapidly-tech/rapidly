/**
 * Fetch wrappers for the Screen chamber backend endpoints (PR 5).
 *
 * The backend mounts the screen router at ``/api/v1/screen/*``; these
 * wrappers keep the URL construction and status-code → Error mapping out
 * of the hook layer.
 */

const SCREEN_API = '/api/v1/screen'

export class ScreenApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ScreenApiError'
  }
}

export class ScreenDisabledError extends ScreenApiError {
  constructor() {
    super(404, 'Screen sharing is not enabled on this deployment.')
    this.name = 'ScreenDisabledError'
  }
}

export interface CreateSessionResponse {
  short_slug: string
  long_slug: string
  secret: string
  invite_template: string
  expires_at: string
}

export interface MintInviteResponse {
  invite_token: string
  invite_url: string
}

export interface ScreenSessionPublicView {
  short_slug: string
  title: string | null
  max_viewers: number
  started_at: string | null
  host_connected: boolean
}

export async function createSession(
  title: string | null,
  maxViewers: number,
): Promise<CreateSessionResponse> {
  const body: Record<string, unknown> = { max_viewers: maxViewers }
  if (title) body.title = title
  const res = await fetch(`${SCREEN_API}/session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(body),
  })
  if (res.status === 404) throw new ScreenDisabledError()
  if (!res.ok) {
    throw new ScreenApiError(res.status, `createSession failed: ${res.status}`)
  }
  return (await res.json()) as CreateSessionResponse
}

export async function mintInvite(
  slug: string,
  secret: string,
): Promise<MintInviteResponse> {
  const res = await fetch(`${SCREEN_API}/session/${slug}/invite`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ secret }),
  })
  if (!res.ok) {
    throw new ScreenApiError(res.status, `mintInvite failed: ${res.status}`)
  }
  return (await res.json()) as MintInviteResponse
}

export async function getPublicView(
  slug: string,
): Promise<ScreenSessionPublicView> {
  const res = await fetch(`${SCREEN_API}/session/${slug}`, {
    credentials: 'include',
  })
  if (res.status === 404) {
    throw new ScreenApiError(404, 'Session not found or expired.')
  }
  if (!res.ok) {
    throw new ScreenApiError(res.status, `getPublicView failed: ${res.status}`)
  }
  return (await res.json()) as ScreenSessionPublicView
}

export async function closeSession(
  slug: string,
  secret: string,
): Promise<void> {
  const res = await fetch(`${SCREEN_API}/session/${slug}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ secret }),
  })
  if (!res.ok && res.status !== 204) {
    throw new ScreenApiError(res.status, `closeSession failed: ${res.status}`)
  }
}
