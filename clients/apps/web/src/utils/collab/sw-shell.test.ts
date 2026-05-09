import { describe, expect, it } from 'vitest'

import {
  CACHE_NAME,
  COLLAB_CACHE_PREFIX,
  expiredCaches,
  PRECACHE_URLS,
  shouldServeCacheFirst,
  shouldServeNetworkFirst,
} from './sw-shell'

describe('CACHE_NAME', () => {
  it('starts with the shared prefix so expired-cache sweeps match', () => {
    expect(CACHE_NAME.startsWith(COLLAB_CACHE_PREFIX)).toBe(true)
  })
})

describe('PRECACHE_URLS', () => {
  it('contains the root HTML + the manifest + an icon', () => {
    expect(PRECACHE_URLS).toContain('/')
    expect(PRECACHE_URLS).toContain('/site.webmanifest')
    expect(PRECACHE_URLS.some((u) => /icon|favicon/.test(u))).toBe(true)
  })

  it('every entry is an absolute path starting with /', () => {
    for (const u of PRECACHE_URLS) {
      expect(u.startsWith('/')).toBe(true)
    }
  })
})

describe('shouldServeNetworkFirst', () => {
  it('destination=document always wins', () => {
    expect(
      shouldServeNetworkFirst('https://rapidly.tech/collab/abc', 'document'),
    ).toBe(true)
  })

  it('pretty URLs without destination fall through to the accept heuristic', () => {
    expect(
      shouldServeNetworkFirst('https://rapidly.tech/collab/abc', undefined),
    ).toBe(true)
  })

  it('returns false for /_next/ URLs (let cache-first take them)', () => {
    expect(
      shouldServeNetworkFirst(
        'https://rapidly.tech/_next/static/chunks/app.js',
        undefined,
      ),
    ).toBe(false)
  })

  it('returns false for obvious static file extensions', () => {
    const cases = [
      'https://rapidly.tech/icon-192.png',
      'https://rapidly.tech/favicon.svg',
      'https://rapidly.tech/fonts/inter.woff2',
      'https://rapidly.tech/site.webmanifest',
    ]
    for (const url of cases) {
      expect(shouldServeNetworkFirst(url, undefined)).toBe(false)
    }
  })

  it('returns false on malformed URLs rather than throwing', () => {
    expect(shouldServeNetworkFirst('not a url', undefined)).toBe(false)
  })
})

describe('shouldServeCacheFirst', () => {
  it('matches the hashed /_next/static/ tree', () => {
    expect(
      shouldServeCacheFirst('https://rapidly.tech/_next/static/chunks/app.js'),
    ).toBe(true)
  })

  it('matches static assets at the root', () => {
    const cases = [
      'https://rapidly.tech/icon-192.png',
      'https://rapidly.tech/favicon.svg',
      'https://rapidly.tech/fonts/inter.woff2',
      'https://rapidly.tech/site.webmanifest',
    ]
    for (const url of cases) {
      expect(shouldServeCacheFirst(url)).toBe(true)
    }
  })

  it('does not match HTML navigations', () => {
    expect(shouldServeCacheFirst('https://rapidly.tech/collab/abc')).toBe(false)
    expect(shouldServeCacheFirst('https://rapidly.tech/')).toBe(false)
  })

  it('does not match API calls', () => {
    expect(
      shouldServeCacheFirst('https://rapidly.tech/api/v1/collab/sessions'),
    ).toBe(false)
  })

  it('returns false on malformed URLs rather than throwing', () => {
    expect(shouldServeCacheFirst('not a url')).toBe(false)
  })
})

describe('expiredCaches', () => {
  it('keeps the current version, drops other versions with the same prefix', () => {
    const existing = [
      `${COLLAB_CACHE_PREFIX}v1`,
      `${COLLAB_CACHE_PREFIX}v0`,
      `${COLLAB_CACHE_PREFIX}v0-beta`,
    ]
    expect(expiredCaches(existing, 'v1')).toEqual([
      `${COLLAB_CACHE_PREFIX}v0`,
      `${COLLAB_CACHE_PREFIX}v0-beta`,
    ])
  })

  it('leaves caches from other modules alone (e.g. StreamSaver)', () => {
    const existing = [
      `${COLLAB_CACHE_PREFIX}v1`,
      'streamsaver-files-v2',
      'workbox-precache',
    ]
    expect(expiredCaches(existing, 'v1')).toEqual([])
  })

  it('empty list returns empty', () => {
    expect(expiredCaches([], 'v1')).toEqual([])
  })
})
