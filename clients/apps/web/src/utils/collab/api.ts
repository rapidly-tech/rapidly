/**
 * Fetch wrappers for the Collab chamber backend (PR 16).
 *
 * Mirrors ``utils/call/api.ts`` — same error types, same shape.
 */

const COLLAB_API = '/api/v1/collab'

export class CollabApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'CollabApiError'
  }
}

export class CollabDisabledError extends CollabApiError {
  constructor() {
    super(404, 'Collab is not enabled on this deployment.')
    this.name = 'CollabDisabledError'
  }
}

export type CollabKind = 'text' | 'canvas'

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

export interface CollabSessionPublicView {
  short_slug: string
  title: string | null
  max_participants: number
  kind: CollabKind
  started_at: string | null
  host_connected: boolean
}

export async function createSession(
  title: string | null,
  maxParticipants: number,
  kind: CollabKind,
): Promise<CreateSessionResponse> {
  const body: Record<string, unknown> = {
    max_participants: maxParticipants,
    kind,
  }
  if (title) body.title = title
  const res = await fetch(`${COLLAB_API}/session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(body),
  })
  if (res.status === 404) throw new CollabDisabledError()
  if (!res.ok) {
    throw new CollabApiError(res.status, `createSession failed: ${res.status}`)
  }
  return (await res.json()) as CreateSessionResponse
}

export async function mintInvite(
  slug: string,
  secret: string,
): Promise<MintInviteResponse> {
  const res = await fetch(`${COLLAB_API}/session/${slug}/invite`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ secret }),
  })
  if (!res.ok) {
    throw new CollabApiError(res.status, `mintInvite failed: ${res.status}`)
  }
  return (await res.json()) as MintInviteResponse
}

export async function getPublicView(
  slug: string,
): Promise<CollabSessionPublicView> {
  const res = await fetch(`${COLLAB_API}/session/${slug}`, {
    credentials: 'include',
  })
  if (res.status === 404) {
    throw new CollabApiError(404, 'Session not found or expired.')
  }
  if (!res.ok) {
    throw new CollabApiError(res.status, `getPublicView failed: ${res.status}`)
  }
  return (await res.json()) as CollabSessionPublicView
}

export async function closeSession(
  slug: string,
  secret: string,
): Promise<void> {
  const res = await fetch(`${COLLAB_API}/session/${slug}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ secret }),
  })
  if (!res.ok && res.status !== 204) {
    throw new CollabApiError(res.status, `closeSession failed: ${res.status}`)
  }
}
