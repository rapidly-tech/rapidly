/**
 * Fetch wrappers for the Watch chamber backend (PR 9).
 *
 * Mirrors ``utils/screen/api.ts`` — same error types, same shape — so
 * the two chambers' UI layers stay interchangeable where they can.
 */

const WATCH_API = '/api/v1/watch'

export class WatchApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'WatchApiError'
  }
}

export class WatchDisabledError extends WatchApiError {
  constructor() {
    super(404, 'Watch Together is not enabled on this deployment.')
    this.name = 'WatchDisabledError'
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

export interface WatchSessionPublicView {
  short_slug: string
  title: string | null
  max_viewers: number
  source_url: string | null
  source_kind: string
  started_at: string | null
  host_connected: boolean
}

export async function createSession(
  title: string | null,
  maxViewers: number,
  sourceUrl: string | null,
): Promise<CreateSessionResponse> {
  const body: Record<string, unknown> = { max_viewers: maxViewers }
  if (title) body.title = title
  if (sourceUrl) body.source_url = sourceUrl
  const res = await fetch(`${WATCH_API}/session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(body),
  })
  if (res.status === 404) throw new WatchDisabledError()
  if (!res.ok) {
    throw new WatchApiError(res.status, `createSession failed: ${res.status}`)
  }
  return (await res.json()) as CreateSessionResponse
}

export async function mintInvite(
  slug: string,
  secret: string,
): Promise<MintInviteResponse> {
  const res = await fetch(`${WATCH_API}/session/${slug}/invite`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ secret }),
  })
  if (!res.ok) {
    throw new WatchApiError(res.status, `mintInvite failed: ${res.status}`)
  }
  return (await res.json()) as MintInviteResponse
}

export async function getPublicView(
  slug: string,
): Promise<WatchSessionPublicView> {
  const res = await fetch(`${WATCH_API}/session/${slug}`, {
    credentials: 'include',
  })
  if (res.status === 404) {
    throw new WatchApiError(404, 'Session not found or expired.')
  }
  if (!res.ok) {
    throw new WatchApiError(res.status, `getPublicView failed: ${res.status}`)
  }
  return (await res.json()) as WatchSessionPublicView
}

export async function closeSession(
  slug: string,
  secret: string,
): Promise<void> {
  const res = await fetch(`${WATCH_API}/session/${slug}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ secret }),
  })
  if (!res.ok && res.status !== 204) {
    throw new WatchApiError(res.status, `closeSession failed: ${res.status}`)
  }
}
