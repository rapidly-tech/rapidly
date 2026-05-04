/**
 * Unit tests for the Watch chamber fetch wrappers.
 *
 * Mirrors ``utils/screen/api.test.ts`` + siblings. Watch-specific bits:
 *  - ``createSession`` accepts an optional ``source_url`` body field
 *    so hosts can preseed the player before anyone joins.
 *  - ``getPublicView`` exposes ``source_kind`` alongside ``source_url``
 *    so the guest picks the right player before the host's first
 *    awareness payload lands.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  WatchApiError,
  WatchDisabledError,
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
  it('POSTs to /api/v1/watch/session with max_viewers + optional body fields', async () => {
    const calls = installFetch(
      () =>
        new Response(
          JSON.stringify({
            short_slug: 'abc',
            long_slug: 'abcd-efgh',
            secret: 'sec',
            invite_template: '/watch/abc?t={token}',
            expires_at: '2026-04-22T22:00:00Z',
          }),
          { status: 200 },
        ),
    )
    const out = await createSession(
      'Movie night',
      8,
      'https://youtu.be/dQw4w9WgXcQ',
    )
    expect(out.short_slug).toBe('abc')
    expect(calls[0]!.url).toBe('/api/v1/watch/session')
    expect(calls[0]!.init?.method).toBe('POST')
    expect(calls[0]!.init?.credentials).toBe('include')
    expect(JSON.parse(calls[0]!.init!.body as string)).toEqual({
      max_viewers: 8,
      title: 'Movie night',
      source_url: 'https://youtu.be/dQw4w9WgXcQ',
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
    await createSession(null, 3, 'https://example.com/vid.mp4')
    const body = JSON.parse(calls[0]!.init!.body as string) as Record<
      string,
      unknown
    >
    expect(body.title).toBeUndefined()
    expect(body.max_viewers).toBe(3)
    expect(body.source_url).toBe('https://example.com/vid.mp4')
  })

  it('omits source_url when null (host can pick the source in-session)', async () => {
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
    await createSession('Later', 2, null)
    const body = JSON.parse(calls[0]!.init!.body as string) as Record<
      string,
      unknown
    >
    expect(body.source_url).toBeUndefined()
    expect(body.title).toBe('Later')
  })

  it('throws WatchDisabledError on 404 (flag off)', async () => {
    installFetch(() => new Response('', { status: 404 }))
    await expect(createSession(null, 4, null)).rejects.toBeInstanceOf(
      WatchDisabledError,
    )
  })

  it('throws WatchApiError on other non-2xx', async () => {
    installFetch(() => new Response('', { status: 500 }))
    const err = await createSession(null, 4, null).catch((e) => e)
    expect(err).toBeInstanceOf(WatchApiError)
    expect((err as WatchApiError).status).toBe(500)
  })
})

describe('mintInvite', () => {
  it('POSTs the host secret to /session/{slug}/invite', async () => {
    const calls = installFetch(
      () =>
        new Response(
          JSON.stringify({
            invite_token: 'tok',
            invite_url: '/watch/abc?t=tok',
          }),
          { status: 200 },
        ),
    )
    const out = await mintInvite('abc', 'the-secret')
    expect(out.invite_token).toBe('tok')
    expect(calls[0]!.url).toBe('/api/v1/watch/session/abc/invite')
    expect(calls[0]!.init?.method).toBe('POST')
    expect(JSON.parse(calls[0]!.init!.body as string)).toEqual({
      secret: 'the-secret',
    })
  })

  it('rejects with WatchApiError (not Disabled) on 401 bad secret', async () => {
    installFetch(() => new Response('', { status: 401 }))
    const err = await mintInvite('abc', 'wrong').catch((e) => e)
    expect(err).toBeInstanceOf(WatchApiError)
    expect(err).not.toBeInstanceOf(WatchDisabledError)
    expect((err as WatchApiError).status).toBe(401)
  })
})

describe('getPublicView', () => {
  it('GETs session metadata including source_url + source_kind', async () => {
    const calls = installFetch(
      () =>
        new Response(
          JSON.stringify({
            short_slug: 'abc',
            title: 'Movie night',
            max_viewers: 8,
            source_url: 'https://youtu.be/dQw4w9WgXcQ',
            source_kind: 'youtube',
            started_at: '2026-04-22T22:00:00Z',
            host_connected: true,
          }),
          { status: 200 },
        ),
    )
    const view = await getPublicView('abc')
    expect(view.source_kind).toBe('youtube')
    expect(view.source_url).toBe('https://youtu.be/dQw4w9WgXcQ')
    expect(view.host_connected).toBe(true)
    expect(calls[0]!.url).toBe('/api/v1/watch/session/abc')
    expect(calls[0]!.init?.method ?? 'GET').toBe('GET')
    expect(calls[0]!.init?.credentials).toBe('include')
  })

  it('throws with status 404 when the session is missing or expired', async () => {
    installFetch(() => new Response('', { status: 404 }))
    const err = await getPublicView('nope').catch((e) => e)
    expect(err).toBeInstanceOf(WatchApiError)
    expect((err as WatchApiError).status).toBe(404)
    expect((err as Error).message).toContain('expired')
  })

  it('throws WatchApiError on 500', async () => {
    installFetch(() => new Response('', { status: 500 }))
    await expect(getPublicView('x')).rejects.toBeInstanceOf(WatchApiError)
  })
})

describe('closeSession', () => {
  it('DELETEs with secret body and succeeds on 204', async () => {
    const calls = installFetch(() => new Response(null, { status: 204 }))
    await closeSession('abc', 'sec')
    expect(calls[0]!.url).toBe('/api/v1/watch/session/abc')
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
    await expect(closeSession('x', 'y')).rejects.toBeInstanceOf(WatchApiError)
  })
})

describe('error types', () => {
  it('WatchDisabledError extends WatchApiError with status 404', () => {
    const err = new WatchDisabledError()
    expect(err).toBeInstanceOf(WatchApiError)
    expect(err.status).toBe(404)
    expect(err.name).toBe('WatchDisabledError')
    expect(err.message).toContain('Watch Together')
  })

  it('WatchApiError preserves status + message + name', () => {
    const err = new WatchApiError(429, 'rate limited')
    expect(err.status).toBe(429)
    expect(err.message).toBe('rate limited')
    expect(err.name).toBe('WatchApiError')
    expect(err).toBeInstanceOf(Error)
  })
})
