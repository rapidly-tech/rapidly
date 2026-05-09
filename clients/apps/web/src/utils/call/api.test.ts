/**
 * Unit tests for the Call chamber fetch wrappers.
 *
 * Mirrors ``utils/screen/api.test.ts`` + ``utils/collab/api.test.ts``
 * — URL construction, body shape, and status-code → Error mapping are
 * the contract. Hand-rolled fetch stub keeps the module decoupled from
 * any HTTP mocking lib.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  CallApiError,
  CallDisabledError,
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
  globalThis.fetch = vi.fn().mockRejectedValue(new Error('fetch not stubbed'))
})

describe('createSession', () => {
  it('POSTs to /api/v1/call/session with max_participants + mode', async () => {
    const calls = installFetch(
      () =>
        new Response(
          JSON.stringify({
            short_slug: 'abc',
            long_slug: 'abcd-efgh',
            secret: 'sec',
            invite_template: '/call/abc?t={token}',
            expires_at: '2026-04-22T22:00:00Z',
          }),
          { status: 200 },
        ),
    )
    const out = await createSession('Standup', 6, 'audio_video')
    expect(out.short_slug).toBe('abc')
    expect(out.secret).toBe('sec')
    expect(calls[0]!.url).toBe('/api/v1/call/session')
    expect(calls[0]!.init?.method).toBe('POST')
    expect(calls[0]!.init?.credentials).toBe('include')
    expect(JSON.parse(calls[0]!.init!.body as string)).toEqual({
      max_participants: 6,
      mode: 'audio_video',
      title: 'Standup',
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
    await createSession(null, 2, 'audio_only')
    const body = JSON.parse(calls[0]!.init!.body as string) as Record<
      string,
      unknown
    >
    expect(body.title).toBeUndefined()
    expect(body.max_participants).toBe(2)
    expect(body.mode).toBe('audio_only')
  })

  it('throws CallDisabledError on 404 (flag off)', async () => {
    installFetch(() => new Response('', { status: 404 }))
    await expect(createSession(null, 4, 'audio_video')).rejects.toBeInstanceOf(
      CallDisabledError,
    )
  })

  it('throws CallApiError on other non-2xx', async () => {
    installFetch(() => new Response('', { status: 500 }))
    const err = await createSession(null, 4, 'audio_video').catch((e) => e)
    expect(err).toBeInstanceOf(CallApiError)
    expect((err as CallApiError).status).toBe(500)
  })
})

describe('mintInvite', () => {
  it('POSTs the host secret to /session/{slug}/invite', async () => {
    const calls = installFetch(
      () =>
        new Response(
          JSON.stringify({
            invite_token: 'tok',
            invite_url: '/call/abc?t=tok',
          }),
          { status: 200 },
        ),
    )
    const out = await mintInvite('abc', 'the-secret')
    expect(out.invite_token).toBe('tok')
    expect(out.invite_url).toBe('/call/abc?t=tok')
    expect(calls[0]!.url).toBe('/api/v1/call/session/abc/invite')
    expect(calls[0]!.init?.method).toBe('POST')
    expect(JSON.parse(calls[0]!.init!.body as string)).toEqual({
      secret: 'the-secret',
    })
  })

  it('rejects with CallApiError (not Disabled) on 401 bad secret', async () => {
    installFetch(() => new Response('', { status: 401 }))
    const err = await mintInvite('abc', 'wrong').catch((e) => e)
    expect(err).toBeInstanceOf(CallApiError)
    expect(err).not.toBeInstanceOf(CallDisabledError)
    expect((err as CallApiError).status).toBe(401)
  })
})

describe('getPublicView', () => {
  it('GETs session metadata and returns it typed', async () => {
    const calls = installFetch(
      () =>
        new Response(
          JSON.stringify({
            short_slug: 'abc',
            title: 'Team sync',
            max_participants: 4,
            mode: 'audio_video',
            started_at: '2026-04-22T22:00:00Z',
            host_connected: true,
          }),
          { status: 200 },
        ),
    )
    const view = await getPublicView('abc')
    expect(view.short_slug).toBe('abc')
    expect(view.mode).toBe('audio_video')
    expect(view.host_connected).toBe(true)
    expect(calls[0]!.url).toBe('/api/v1/call/session/abc')
    expect(calls[0]!.init?.method ?? 'GET').toBe('GET')
    expect(calls[0]!.init?.credentials).toBe('include')
  })

  it('throws with status 404 when the session is missing or expired', async () => {
    installFetch(() => new Response('', { status: 404 }))
    const err = await getPublicView('nope').catch((e) => e)
    expect(err).toBeInstanceOf(CallApiError)
    expect((err as CallApiError).status).toBe(404)
    expect((err as Error).message).toContain('expired')
  })

  it('throws CallApiError on 500', async () => {
    installFetch(() => new Response('', { status: 500 }))
    await expect(getPublicView('x')).rejects.toBeInstanceOf(CallApiError)
  })
})

describe('closeSession', () => {
  it('DELETEs with the secret body and succeeds on 204', async () => {
    const calls = installFetch(() => new Response(null, { status: 204 }))
    await closeSession('abc', 'sec')
    expect(calls[0]!.url).toBe('/api/v1/call/session/abc')
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
    await expect(closeSession('x', 'y')).rejects.toBeInstanceOf(CallApiError)
  })
})

describe('error types', () => {
  it('CallDisabledError extends CallApiError with status 404', () => {
    const err = new CallDisabledError()
    expect(err).toBeInstanceOf(CallApiError)
    expect(err.status).toBe(404)
    expect(err.name).toBe('CallDisabledError')
  })

  it('CallApiError preserves status + message + name', () => {
    const err = new CallApiError(429, 'rate limited')
    expect(err.status).toBe(429)
    expect(err.message).toBe('rate limited')
    expect(err.name).toBe('CallApiError')
    expect(err).toBeInstanceOf(Error)
  })
})
