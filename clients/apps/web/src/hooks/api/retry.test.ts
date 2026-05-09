import {
  ApiResponseError,
  AuthenticationError,
  ResourceNotFoundError,
} from '@rapidly-tech/client'
import { describe, expect, it } from 'vitest'

import { baseRetry } from './retry'

/** Tiny helpers to build the error classes with a Response that has a
 *  specific status. ``ApiResponseError.error`` is typed ``any`` — we
 *  only need ``message`` for the super constructor. */
function apiError(status: number, message = 'oops'): ApiResponseError {
  return new ApiResponseError({ message }, new Response('', { status }))
}

function authError(): AuthenticationError {
  return new AuthenticationError(
    { message: 'auth' },
    new Response('', { status: 401 }),
  )
}

function notFoundError(): ResourceNotFoundError {
  return new ResourceNotFoundError(
    { message: 'missing' },
    new Response('', { status: 404 }),
  )
}

describe('baseRetry — terminal error classes', () => {
  it('never retries on AuthenticationError (401)', () => {
    expect(baseRetry(0, authError())).toBe(false)
    expect(baseRetry(1, authError())).toBe(false)
    expect(baseRetry(2, authError())).toBe(false)
  })

  it('never retries on ResourceNotFoundError (404)', () => {
    expect(baseRetry(0, notFoundError())).toBe(false)
    expect(baseRetry(1, notFoundError())).toBe(false)
  })

  it('never retries on any 4xx ApiResponseError', () => {
    for (const status of [400, 403, 405, 409, 418, 422, 429]) {
      expect(baseRetry(0, apiError(status))).toBe(false)
    }
  })
})

describe('baseRetry — 5xx / network / transient errors', () => {
  it('retries on 500 up to attempt 2', () => {
    expect(baseRetry(0, apiError(500))).toBe(true)
    expect(baseRetry(1, apiError(500))).toBe(true)
    expect(baseRetry(2, apiError(500))).toBe(true)
  })

  it('stops retrying on attempt 3 (after 3 attempts)', () => {
    expect(baseRetry(3, apiError(500))).toBe(false)
    expect(baseRetry(4, apiError(500))).toBe(false)
  })

  it('retries on other 5xx status codes', () => {
    for (const status of [500, 502, 503, 504]) {
      expect(baseRetry(0, apiError(status))).toBe(true)
    }
  })
})

describe('baseRetry — non-integer response status', () => {
  it('treats a response without a truthy status as retriable', () => {
    // The real fetch Response has a 200-599 constraint, but the retry
    // predicate's guard is ``if (status && status >= 400 && status < 500)``
    // — so any falsy or out-of-range status skips the 4xx guard and
    // falls through to the attempt<=2 retry path. Simulate with a
    // minimal stand-in so we don't have to construct a real Response
    // with an exotic status.
    const err = Object.create(ApiResponseError.prototype) as ApiResponseError
    ;(err as { response: unknown }).response = { status: 0 } as Response
    expect(baseRetry(0, err)).toBe(true)
    expect(baseRetry(2, err)).toBe(true)
    expect(baseRetry(3, err)).toBe(false)
  })
})
