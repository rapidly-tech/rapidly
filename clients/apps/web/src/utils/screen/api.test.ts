/**
 * Unit tests for the Screen fetch wrappers.
 *
 * Exercises URL construction and status-code → Error mapping. Uses a
 * hand-rolled fetch stub so the module remains decoupled from any HTTP
 * mocking library.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  ScreenApiError,
  ScreenDisabledError,
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
  // jsdom gives us no default fetch — ensure tests that forget to stub fail loudly.
  globalThis.fetch = vi.fn().mockRejectedValue(new Error('fetch not stubbed'))
})

describe('createSession', () => {
  it('POSTs to /api/v1/screen/session with the body', async () => {
    const calls = installFetch(
      () =>
        new Response(
          JSON.stringify({
            short_slug: 's1',
            long_slug: 'ssss-1',
            secret: 'sec',
            invite_template: '/screen/s1?t={token}',
            expires_at: '2026-04-17T23:00:00Z',
          }),
          { status: 200 },
        ),
    )
    const out = await createSession('Demo', 5)
    expect(out.short_slug).toBe('s1')
    expect(calls[0]!.url).toBe('/api/v1/screen/session')
    expect(calls[0]!.init?.method).toBe('POST')
    expect(JSON.parse(calls[0]!.init!.body as string)).toEqual({
      max_viewers: 5,
      title: 'Demo',
    })
  })

  it('throws ScreenDisabledError on 404', async () => {
    installFetch(() => new Response('', { status: 404 }))
    await expect(createSession(null, 5)).rejects.toBeInstanceOf(
      ScreenDisabledError,
    )
  })

  it('throws ScreenApiError on other non-2xx', async () => {
    installFetch(() => new Response('', { status: 500 }))
    await expect(createSession(null, 5)).rejects.toBeInstanceOf(ScreenApiError)
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
    await createSession(null, 3)
    const body = JSON.parse(calls[0]!.init!.body as string) as Record<
      string,
      unknown
    >
    expect(body.title).toBeUndefined()
    expect(body.max_viewers).toBe(3)
  })
})

describe('mintInvite', () => {
  it('POSTs secret and returns the token payload', async () => {
    const calls = installFetch(
      () =>
        new Response(
          JSON.stringify({
            invite_token: 'tok',
            invite_url: '/screen/abc?t=tok',
          }),
          { status: 200 },
        ),
    )
    const out = await mintInvite('abc', 'the-secret')
    expect(out.invite_token).toBe('tok')
    expect(calls[0]!.url).toBe('/api/v1/screen/session/abc/invite')
    expect(JSON.parse(calls[0]!.init!.body as string)).toEqual({
      secret: 'the-secret',
    })
  })

  it('throws on 404 (wrong secret or missing slug)', async () => {
    installFetch(() => new Response('', { status: 404 }))
    await expect(mintInvite('x', 'wrong')).rejects.toBeInstanceOf(
      ScreenApiError,
    )
  })
})

describe('getPublicView', () => {
  it('GETs session metadata and returns it typed', async () => {
    installFetch(
      () =>
        new Response(
          JSON.stringify({
            short_slug: 'x',
            title: 'Standup',
            max_viewers: 7,
            started_at: '2026-04-17T22:00:00Z',
            host_connected: true,
          }),
          { status: 200 },
        ),
    )
    const view = await getPublicView('x')
    expect(view.short_slug).toBe('x')
    expect(view.host_connected).toBe(true)
  })

  it('throws a 404 error when session is missing', async () => {
    installFetch(() => new Response('', { status: 404 }))
    await expect(getPublicView('nope')).rejects.toMatchObject({ status: 404 })
  })
})

describe('closeSession', () => {
  it('DELETEs with secret body and succeeds on 204', async () => {
    const calls = installFetch(() => new Response(null, { status: 204 }))
    await closeSession('abc', 'sec')
    expect(calls[0]!.url).toBe('/api/v1/screen/session/abc')
    expect(calls[0]!.init?.method).toBe('DELETE')
    expect(JSON.parse(calls[0]!.init!.body as string)).toEqual({
      secret: 'sec',
    })
  })

  it('throws on 500', async () => {
    installFetch(() => new Response('', { status: 500 }))
    await expect(closeSession('x', 'y')).rejects.toBeInstanceOf(ScreenApiError)
  })
})
