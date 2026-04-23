import {
  ApiResponseError,
  AuthenticationError,
  RateLimitError,
  ResourceNotFoundError,
  isValidationError,
  resolveResponse,
} from '@rapidly-tech/client'
import { describe, expect, it } from 'vitest'

/** Tests live in the web app (not the ``@rapidly-tech/client`` package)
 *  so they can share the app's existing vitest setup — the client
 *  package has no test script of its own. These pin the error-class
 *  hierarchy + ``resolveResponse`` status → error mapping + the
 *  ``isValidationError`` type guard that every API call-site uses. */

describe('error classes', () => {
  it('ApiResponseError preserves message + response + name', () => {
    const resp = new Response('', { status: 500 })
    const err = new ApiResponseError({ message: 'boom' }, resp)
    expect(err.message).toBe('boom')
    expect(err.response).toBe(resp)
    expect(err.name).toBe('ApiResponseError')
    expect(err).toBeInstanceOf(Error)
  })

  it('AuthenticationError extends ApiResponseError with its own name', () => {
    const err = new AuthenticationError(
      { message: 'unauth' },
      new Response('', { status: 401 }),
    )
    expect(err).toBeInstanceOf(ApiResponseError)
    expect(err.name).toBe('AuthenticationError')
    expect(err.message).toBe('unauth')
  })

  it('ResourceNotFoundError extends ApiResponseError with its own name', () => {
    const err = new ResourceNotFoundError(
      { message: 'missing' },
      new Response('', { status: 404 }),
    )
    expect(err).toBeInstanceOf(ApiResponseError)
    expect(err.name).toBe('ResourceNotFoundError')
  })

  it('RateLimitError extends ApiResponseError with its own name', () => {
    const err = new RateLimitError(
      { message: 'rl' },
      new Response('', { status: 429 }),
    )
    expect(err).toBeInstanceOf(ApiResponseError)
    expect(err.name).toBe('RateLimitError')
  })
})

describe('resolveResponse — success path', () => {
  it('returns the data on a successful fetch', async () => {
    const p = Promise.resolve({
      data: { hello: 'world' },
      error: undefined,
      response: new Response('', { status: 200 }),
    })
    const result = await resolveResponse(
      p as unknown as Parameters<typeof resolveResponse>[0],
    )
    expect(result).toEqual({ hello: 'world' })
  })

  it('throws "No data returned" when response succeeds but data is falsy', async () => {
    const p = Promise.resolve({
      data: undefined,
      error: undefined,
      response: new Response(null, { status: 204 }),
    })
    await expect(
      resolveResponse(p as unknown as Parameters<typeof resolveResponse>[0]),
    ).rejects.toThrow(/No data returned/)
  })
})

describe('resolveResponse — error status mapping', () => {
  it('maps 401 → AuthenticationError', async () => {
    const p = Promise.resolve({
      data: undefined,
      error: { detail: 'unauth' },
      response: new Response('', { status: 401 }),
    })
    await expect(
      resolveResponse(p as unknown as Parameters<typeof resolveResponse>[0]),
    ).rejects.toBeInstanceOf(AuthenticationError)
  })

  it('maps 404 → ResourceNotFoundError', async () => {
    const p = Promise.resolve({
      data: undefined,
      error: { detail: 'missing' },
      response: new Response('', { status: 404 }),
    })
    await expect(
      resolveResponse(p as unknown as Parameters<typeof resolveResponse>[0]),
    ).rejects.toBeInstanceOf(ResourceNotFoundError)
  })

  it('maps 429 → RateLimitError even when error is absent', async () => {
    // 429 is special — thrown before the error-field check, so the
    // server doesn't need to return a body.
    const p = Promise.resolve({
      data: undefined,
      error: undefined,
      response: new Response('', { status: 429 }),
    })
    await expect(
      resolveResponse(p as unknown as Parameters<typeof resolveResponse>[0]),
    ).rejects.toBeInstanceOf(RateLimitError)
  })

  it('maps other non-2xx status codes → plain ApiResponseError', async () => {
    const p = Promise.resolve({
      data: undefined,
      error: { detail: 'server broken' },
      response: new Response('', { status: 500 }),
    })
    const err = await resolveResponse(
      p as unknown as Parameters<typeof resolveResponse>[0],
    ).catch((e) => e)
    expect(err).toBeInstanceOf(ApiResponseError)
    expect(err).not.toBeInstanceOf(AuthenticationError)
    expect(err).not.toBeInstanceOf(ResourceNotFoundError)
    expect(err).not.toBeInstanceOf(RateLimitError)
  })
})

describe('resolveResponse — status handlers', () => {
  it('invokes a per-status handler when one matches, bypassing the default mapping', async () => {
    const p = Promise.resolve({
      data: undefined,
      error: { detail: 'custom' },
      response: new Response('', { status: 404 }),
    })
    const sentinel = Symbol('custom') as unknown as never
    const result = await resolveResponse(
      p as unknown as Parameters<typeof resolveResponse>[0],
      {
        404: () => sentinel,
      },
    )
    expect(result).toBe(sentinel)
  })

  it('falls back to default mapping when no handler matches the status', async () => {
    const p = Promise.resolve({
      data: undefined,
      error: { detail: 'unauth' },
      response: new Response('', { status: 401 }),
    })
    await expect(
      resolveResponse(p as unknown as Parameters<typeof resolveResponse>[0], {
        404: () => {
          throw new Error('should not fire')
        },
      }),
    ).rejects.toBeInstanceOf(AuthenticationError)
  })
})

describe('isValidationError', () => {
  // Note: the guard short-circuits through ``&&`` to ``detail[0].loc`` —
  // it returns a truthy value (the loc array) or a falsy value, not a
  // strict boolean. Tests use ``toBeTruthy`` / ``toBeFalsy`` for positive
  // / negative cases so the behaviour is pinned accurately.

  it('accepts a non-empty validation array with loc + msg fields', () => {
    const detail = [
      { loc: ['body', 'email'], msg: 'field required', type: 'missing' },
    ]
    expect(isValidationError(detail)).toBeTruthy()
  })

  it('rejects undefined / null / primitives', () => {
    expect(isValidationError(undefined)).toBeFalsy()
    expect(isValidationError(null)).toBeFalsy()
    expect(isValidationError('string')).toBeFalsy()
    expect(isValidationError(42)).toBeFalsy()
  })

  it('rejects an empty array', () => {
    expect(isValidationError([])).toBeFalsy()
  })

  it('rejects an array whose first element has no loc field', () => {
    expect(isValidationError([{ msg: 'bad' }])).toBeFalsy()
  })

  it('accepts numeric loc segments (list-index validation errors)', () => {
    const detail = [
      { loc: ['body', 'items', 0, 'id'], msg: 'required', type: 'missing' },
    ]
    expect(isValidationError(detail)).toBeTruthy()
  })
})
