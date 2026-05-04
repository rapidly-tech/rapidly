/**
 * Unit tests for the Collab chamber fetch wrappers.
 *
 * Mirrors ``utils/screen/api.test.ts`` — URL construction, body shape,
 * and status-code → Error mapping are the contract. Uses a hand-rolled
 * fetch stub so the module stays decoupled from any HTTP mocking lib.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  CollabApiError,
  CollabDisabledError,
  closeSession,
  createSession,
  getPublicView,
  mintInvite,
} from './api'

interface FetchCall {
  url: string
  init?: RequestInit
}

function installFetch(
  responder: (call: FetchCall) => Response | Promise<Response>,
) {
  const calls: FetchCall[] = []
  globalThis.fetch = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const call = { url: String(input), init }
      calls.push(call)
      return responder(call)
    },
  ) as typeof fetch
  return calls
}

afterEach(() => {
  vi.restoreAllMocks()
})

beforeEach(() => {
  // jsdom has no default fetch — ensure tests that forget to stub fail loudly.
  globalThis.fetch = vi.fn().mockRejectedValue(new Error('fetch not stubbed'))
})

describe('createSession', () => {
  it('POSTs to /api/v1/collab/session with max_participants + kind', async () => {
    const calls = installFetch(
      () =>
        new Response(
          JSON.stringify({
            short_slug: 'abc',
            long_slug: 'abcd-efgh',
            secret: 'sec',
            invite_template: '/collab/abc?t={token}',
            expires_at: '2026-04-22T22:00:00Z',
          }),
          { status: 200 },
        ),
    )
    const out = await createSession('Board', 4, 'canvas')
    expect(out.short_slug).toBe('abc')
    expect(out.secret).toBe('sec')
    expect(calls[0]!.url).toBe('/api/v1/collab/session')
    expect(calls[0]!.init?.method).toBe('POST')
    expect(calls[0]!.init?.credentials).toBe('include')
    expect(JSON.parse(calls[0]!.init!.body as string)).toEqual({
      max_participants: 4,
      kind: 'canvas',
      title: 'Board',
    })
  })

  it('omits title when null', async () => {
    const calls = installFetch(
      () =>
        new Response(
          JSON.stringify({
            short_slug: 's',
            long_slug: 's',
            secret: '',
            invite_template: '',
            expires_at: '',
          }),
          { status: 200 },
        ),
    )
    await createSession(null, 2, 'text')
    const body = JSON.parse(calls[0]!.init!.body as string) as Record<
      string,
      unknown
    >
    expect(body.title).toBeUndefined()
    expect(body.max_participants).toBe(2)
    expect(body.kind).toBe('text')
  })

  it('throws CollabDisabledError on 404 (flag off)', async () => {
    installFetch(() => new Response('', { status: 404 }))
    await expect(createSession(null, 4, 'canvas')).rejects.toBeInstanceOf(
      CollabDisabledError,
    )
  })

  it('throws CollabApiError on other non-2xx', async () => {
    installFetch(() => new Response('', { status: 500 }))
    const err = await createSession(null, 4, 'canvas').catch((e) => e)
    expect(err).toBeInstanceOf(CollabApiError)
    expect((err as CollabApiError).status).toBe(500)
  })
})

describe('mintInvite', () => {
  it('POSTs the host secret to /session/{slug}/invite', async () => {
    const calls = installFetch(
      () =>
        new Response(
          JSON.stringify({
            invite_token: 'tok',
            invite_url: '/collab/abc?t=tok',
          }),
          { status: 200 },
        ),
    )
    const out = await mintInvite('abc', 'the-secret')
    expect(out.invite_token).toBe('tok')
    expect(out.invite_url).toBe('/collab/abc?t=tok')
    expect(calls[0]!.url).toBe('/api/v1/collab/session/abc/invite')
    expect(calls[0]!.init?.method).toBe('POST')
    expect(JSON.parse(calls[0]!.init!.body as string)).toEqual({
      secret: 'the-secret',
    })
  })

  it('rejects with CollabApiError (not Disabled) on 401 bad secret', async () => {
    installFetch(() => new Response('', { status: 401 }))
    const err = await mintInvite('abc', 'wrong').catch((e) => e)
    expect(err).toBeInstanceOf(CollabApiError)
    expect(err).not.toBeInstanceOf(CollabDisabledError)
    expect((err as CollabApiError).status).toBe(401)
  })
})

describe('getPublicView', () => {
  it('GETs session metadata and returns it typed', async () => {
    const calls = installFetch(
      () =>
        new Response(
          JSON.stringify({
            short_slug: 'abc',
            title: 'Standup Board',
            max_participants: 4,
            kind: 'canvas',
            started_at: '2026-04-22T22:00:00Z',
            host_connected: true,
          }),
          { status: 200 },
        ),
    )
    const view = await getPublicView('abc')
    expect(view.short_slug).toBe('abc')
    expect(view.kind).toBe('canvas')
    expect(view.host_connected).toBe(true)
    expect(calls[0]!.url).toBe('/api/v1/collab/session/abc')
    expect(calls[0]!.init?.method ?? 'GET').toBe('GET')
    expect(calls[0]!.init?.credentials).toBe('include')
  })

  it('throws with status 404 when the session is missing or expired', async () => {
    installFetch(() => new Response('', { status: 404 }))
    const err = await getPublicView('nope').catch((e) => e)
    expect(err).toBeInstanceOf(CollabApiError)
    expect((err as CollabApiError).status).toBe(404)
    expect((err as Error).message).toContain('expired')
  })

  it('throws CollabApiError on 500', async () => {
    installFetch(() => new Response('', { status: 500 }))
    await expect(getPublicView('x')).rejects.toBeInstanceOf(CollabApiError)
  })
})

describe('closeSession', () => {
  it('DELETEs with the secret body and succeeds on 204', async () => {
    const calls = installFetch(() => new Response(null, { status: 204 }))
    await closeSession('abc', 'sec')
    expect(calls[0]!.url).toBe('/api/v1/collab/session/abc')
    expect(calls[0]!.init?.method).toBe('DELETE')
    expect(calls[0]!.init?.credentials).toBe('include')
    expect(JSON.parse(calls[0]!.init!.body as string)).toEqual({
      secret: 'sec',
    })
  })

  it('resolves on 200 (some servers return 200 instead of 204)', async () => {
    installFetch(() => new Response('', { status: 200 }))
    await expect(closeSession('abc', 'sec')).resolves.toBeUndefined()
  })

  it('throws on 500', async () => {
    installFetch(() => new Response('', { status: 500 }))
    await expect(closeSession('x', 'y')).rejects.toBeInstanceOf(CollabApiError)
  })
})

describe('error types', () => {
  it('CollabDisabledError extends CollabApiError with status 404', () => {
    const err = new CollabDisabledError()
    expect(err).toBeInstanceOf(CollabApiError)
    expect(err.status).toBe(404)
    expect(err.name).toBe('CollabDisabledError')
  })

  it('CollabApiError preserves status + message + name', () => {
    const err = new CollabApiError(429, 'rate limited')
    expect(err.status).toBe(429)
    expect(err.message).toBe('rate limited')
    expect(err.name).toBe('CollabApiError')
    expect(err).toBeInstanceOf(Error)
  })
})
