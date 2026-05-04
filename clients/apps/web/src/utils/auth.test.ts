import { describe, expect, it } from 'vitest'

import {
  getAppleAuthorizeURL,
  getGoogleAuthorizeLinkURL,
  getGoogleAuthorizeLoginURL,
  getMicrosoftAuthorizeLinkURL,
  getMicrosoftAuthorizeLoginURL,
} from './auth'

/** Assertions focus on path + query shape rather than the absolute host
 *  — the base URL comes from ``NEXT_PUBLIC_API_URL`` and varies across
 *  environments. */

/** Parse the URL's path + sorted query params as a single canonical
 *  string so key ordering doesn't flap the test. */
function canonicalize(url: string): { path: string; query: string[] } {
  // Some bases like ``http://127.0.0.1:8000`` parse fine; a bare ``?...``
  // query with no base is awkward. Always ensure a base by falling back
  // to a dummy origin.
  const u = new URL(url, 'http://example')
  const query = Array.from(u.searchParams.entries())
    .map(([k, v]) => `${k}=${v}`)
    .sort()
  return { path: u.pathname, query }
}

describe('getMicrosoftAuthorizeLoginURL', () => {
  it('hits /api/integrations/microsoft/login/authorize', () => {
    const { path } = canonicalize(
      getMicrosoftAuthorizeLoginURL({ return_to: '/dashboard' }),
    )
    expect(path).toBe('/api/integrations/microsoft/login/authorize')
  })

  it('passes return_to + attribution through to the query', () => {
    const { query } = canonicalize(
      getMicrosoftAuthorizeLoginURL({
        return_to: '/dashboard',
        attribution: 'homepage',
      }),
    )
    expect(query).toEqual(['attribution=homepage', 'return_to=/dashboard'])
  })

  it('omits falsy parameters (null / undefined / empty)', () => {
    const { query } = canonicalize(
      getMicrosoftAuthorizeLoginURL({
        return_to: null,
        attribution: undefined,
      }),
    )
    expect(query).toEqual([])
  })
})

describe('getMicrosoftAuthorizeLinkURL', () => {
  it('hits /api/integrations/microsoft/link/authorize', () => {
    const { path } = canonicalize(
      getMicrosoftAuthorizeLinkURL({ return_to: '/dashboard' }),
    )
    expect(path).toBe('/api/integrations/microsoft/link/authorize')
  })

  it('supports only return_to (no attribution on the link flow)', () => {
    const { query } = canonicalize(
      getMicrosoftAuthorizeLinkURL({ return_to: '/dashboard' }),
    )
    expect(query).toEqual(['return_to=/dashboard'])
  })
})

describe('getGoogleAuthorizeLoginURL', () => {
  it('hits /api/integrations/google/login/authorize with return_to + attribution', () => {
    const { path, query } = canonicalize(
      getGoogleAuthorizeLoginURL({
        return_to: '/next',
        attribution: 'email',
      }),
    )
    expect(path).toBe('/api/integrations/google/login/authorize')
    expect(query).toEqual(['attribution=email', 'return_to=/next'])
  })

  it('omits empty strings', () => {
    const { query } = canonicalize(
      getGoogleAuthorizeLoginURL({ return_to: '', attribution: '' }),
    )
    expect(query).toEqual([])
  })
})

describe('getGoogleAuthorizeLinkURL', () => {
  it('hits /api/integrations/google/link/authorize', () => {
    const { path } = canonicalize(
      getGoogleAuthorizeLinkURL({ return_to: '/settings' }),
    )
    expect(path).toBe('/api/integrations/google/link/authorize')
  })
})

describe('getAppleAuthorizeURL', () => {
  it('hits /api/integrations/apple/authorize with return_to + attribution', () => {
    const { path, query } = canonicalize(
      getAppleAuthorizeURL({
        return_to: '/dashboard',
        attribution: 'landing',
      }),
    )
    expect(path).toBe('/api/integrations/apple/authorize')
    expect(query).toEqual(['attribution=landing', 'return_to=/dashboard'])
  })
})

describe('buildAuthUrl behaviour — round-trip', () => {
  it('URL-encodes reserved characters in query values', () => {
    const url = getMicrosoftAuthorizeLoginURL({
      return_to: '/dashboard?foo=bar&baz=1',
      attribution: 'a&b',
    })
    const u = new URL(url, 'http://example')
    // URLSearchParams handles the encoding; reading back should give
    // the original values intact.
    expect(u.searchParams.get('return_to')).toBe('/dashboard?foo=bar&baz=1')
    expect(u.searchParams.get('attribution')).toBe('a&b')
  })

  it('keeps params stable across multiple calls (no shared state leaks)', () => {
    const a = getMicrosoftAuthorizeLoginURL({ return_to: '/a' })
    const b = getMicrosoftAuthorizeLoginURL({ return_to: '/b' })
    expect(canonicalize(a).query).toEqual(['return_to=/a'])
    expect(canonicalize(b).query).toEqual(['return_to=/b'])
  })
})
