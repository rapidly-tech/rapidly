/**
 * Fetch wrappers for the Call chamber backend (PR 13).
 *
 * Mirrors ``utils/screen/api.ts`` and ``utils/watch/api.ts`` — same
 * error types, same shape.
 */

const CALL_API = '/api/v1/call'

export class CallApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'CallApiError'
  }
}

export class CallDisabledError extends CallApiError {
  constructor() {
    super(404, 'Call is not enabled on this deployment.')
    this.name = 'CallDisabledError'
  }
}

export type CallMode = 'audio_only' | 'audio_video'

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

export interface CallSessionPublicView {
  short_slug: string
  title: string | null
  max_participants: number
  mode: CallMode
  started_at: string | null
  host_connected: boolean
}

export async function createSession(
  title: string | null,
  maxParticipants: number,
  mode: CallMode,
): Promise<CreateSessionResponse> {
  const body: Record<string, unknown> = {
    max_participants: maxParticipants,
    mode,
  }
  if (title) body.title = title
  const res = await fetch(`${CALL_API}/session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(body),
  })
  if (res.status === 404) throw new CallDisabledError()
  if (!res.ok) {
    throw new CallApiError(res.status, `createSession failed: ${res.status}`)
  }
  return (await res.json()) as CreateSessionResponse
}

export async function mintInvite(
  slug: string,
  secret: string,
): Promise<MintInviteResponse> {
  const res = await fetch(`${CALL_API}/session/${slug}/invite`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ secret }),
  })
  if (!res.ok) {
    throw new CallApiError(res.status, `mintInvite failed: ${res.status}`)
  }
  return (await res.json()) as MintInviteResponse
}

export async function getPublicView(
  slug: string,
): Promise<CallSessionPublicView> {
  const res = await fetch(`${CALL_API}/session/${slug}`, {
    credentials: 'include',
  })
  if (res.status === 404) {
    throw new CallApiError(404, 'Session not found or expired.')
  }
  if (!res.ok) {
    throw new CallApiError(res.status, `getPublicView failed: ${res.status}`)
  }
  return (await res.json()) as CallSessionPublicView
}

export async function closeSession(
  slug: string,
  secret: string,
): Promise<void> {
  const res = await fetch(`${CALL_API}/session/${slug}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ secret }),
  })
  if (!res.ok && res.status !== 204) {
    throw new CallApiError(res.status, `closeSession failed: ${res.status}`)
  }
}
