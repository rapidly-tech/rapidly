import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import {
  LARGE_FILE_THRESHOLD,
  VERY_LARGE_FILE_THRESHOLD,
  ZIP64_COUNT_THRESHOLD,
  ZIP64_THRESHOLD,
  buildFileShareURL,
  buildLocalSecretURL,
  buildSecretURL,
  decodeLocalSecretEnvelope,
  encodeLocalSecretEnvelope,
  formatFileSize,
  fromBase64Url,
  toBase64Url,
} from './constants'

describe('constants — numeric thresholds', () => {
  it('ZIP64_THRESHOLD is 0xfffffffe (one below uint32 max)', () => {
    expect(ZIP64_THRESHOLD).toBe(0xfffffffe)
  })

  it('ZIP64_COUNT_THRESHOLD is 0xfffe (one below uint16 max)', () => {
    expect(ZIP64_COUNT_THRESHOLD).toBe(0xfffe)
  })

  it('LARGE_FILE_THRESHOLD is 100 MB', () => {
    expect(LARGE_FILE_THRESHOLD).toBe(100 * 1024 * 1024)
  })

  it('VERY_LARGE_FILE_THRESHOLD is 1 GB', () => {
    expect(VERY_LARGE_FILE_THRESHOLD).toBe(1024 * 1024 * 1024)
  })
})

describe('formatFileSize', () => {
  it('returns "0 B" for zero / negative / non-finite', () => {
    expect(formatFileSize(0)).toBe('0 B')
    expect(formatFileSize(-1)).toBe('0 B')
    expect(formatFileSize(NaN)).toBe('0 B')
    expect(formatFileSize(Infinity)).toBe('0 B')
  })

  it('formats bytes < 1 KB as "B"', () => {
    expect(formatFileSize(1)).toBe('1 B')
    expect(formatFileSize(512)).toBe('512 B')
    expect(formatFileSize(1023)).toBe('1023 B')
  })

  it('formats kilobyte range with one decimal', () => {
    expect(formatFileSize(1024)).toBe('1 KB')
    expect(formatFileSize(1536)).toBe('1.5 KB')
    expect(formatFileSize(1024 * 1023)).toBe('1023 KB')
  })

  it('formats megabyte range', () => {
    expect(formatFileSize(1024 * 1024)).toBe('1 MB')
    expect(formatFileSize(1024 * 1024 * 2.5)).toBe('2.5 MB')
  })

  it('formats gigabyte range', () => {
    expect(formatFileSize(1024 * 1024 * 1024)).toBe('1 GB')
    expect(formatFileSize(1024 * 1024 * 1024 * 1.25)).toBe('1.3 GB') // .toFixed(1) rounds
  })

  it('clamps to TB for values beyond the scale', () => {
    const tb = 1024 ** 4
    expect(formatFileSize(tb)).toBe('1 TB')
    // Beyond TB still formats as TB — the sizes array caps at TB.
    expect(formatFileSize(tb * 5000)).toBe('5000 TB')
  })

  it('strips trailing zeros via parseFloat', () => {
    // 1024 bytes = 1.0 KB; parseFloat turns "1.0" into 1 → "1 KB".
    expect(formatFileSize(1024)).toBe('1 KB')
    expect(formatFileSize(1024 * 1024)).toBe('1 MB')
  })
})

describe('buildFileShareURL', () => {
  const ORIGINAL_ORIGIN =
    typeof window !== 'undefined' && window.location
      ? window.location.origin
      : undefined

  beforeEach(() => {
    // jsdom exposes window.location.origin; we want every test to share
    // the same deterministic origin regardless of whatever jsdom picks.
    if (typeof window !== 'undefined') {
      Object.defineProperty(window, 'location', {
        value: { origin: 'https://rapidly.tech' },
        writable: true,
      })
    }
  })

  afterEach(() => {
    if (typeof window !== 'undefined' && ORIGINAL_ORIGIN !== undefined) {
      Object.defineProperty(window, 'location', {
        value: { origin: ORIGINAL_ORIGIN },
        writable: true,
      })
    }
  })

  it('builds /#/d/{slug}/k/{key}/s/{salt}', () => {
    const url = buildFileShareURL('my-slug', 'base64key', 'base64salt')
    expect(url).toBe(
      'https://rapidly.tech/#/d/my-slug/k/base64key/s/base64salt',
    )
  })

  it('preserves special url-safe chars in key/salt', () => {
    const url = buildFileShareURL('my-slug', 'AbC-_123', 'XyZ-_456')
    expect(url).toBe('https://rapidly.tech/#/d/my-slug/k/AbC-_123/s/XyZ-_456')
  })
})

describe('buildSecretURL', () => {
  beforeEach(() => {
    if (typeof window !== 'undefined') {
      Object.defineProperty(window, 'location', {
        value: { origin: 'https://rapidly.tech' },
        writable: true,
      })
    }
  })

  it('builds /#/s/{uuid} without password', () => {
    expect(buildSecretURL('abc-123')).toBe('https://rapidly.tech/#/s/abc-123')
  })

  it('builds /#/s/{uuid}/{password} when password supplied', () => {
    expect(buildSecretURL('abc-123', 'pw')).toBe(
      'https://rapidly.tech/#/s/abc-123/pw',
    )
  })

  it('omits the password segment when the password is an empty string', () => {
    // Empty string is falsy, so the ternary drops the slash.
    expect(buildSecretURL('abc-123', '')).toBe(
      'https://rapidly.tech/#/s/abc-123',
    )
  })
})

describe('toBase64Url / fromBase64Url', () => {
  it('round-trips ASCII text', () => {
    const input = 'hello world'
    expect(fromBase64Url(toBase64Url(input))).toBe(input)
  })

  it('round-trips multi-line text', () => {
    const input = 'line one\nline two\nline three'
    expect(fromBase64Url(toBase64Url(input))).toBe(input)
  })

  it('round-trips non-ASCII (UTF-8) text', () => {
    const input = 'naïve résumé · 🔐 password'
    expect(fromBase64Url(toBase64Url(input))).toBe(input)
  })

  it('produces URL-safe output (no +, /, or =)', () => {
    // 32 random bytes are likely to hit + and / under standard base64.
    const noisy = String.fromCharCode(
      ...Array.from({ length: 64 }, (_, i) => i + 0x80),
    )
    const out = toBase64Url(noisy)
    expect(out).not.toMatch(/[+/=]/)
  })
})

describe('buildLocalSecretURL', () => {
  beforeEach(() => {
    if (typeof window !== 'undefined') {
      Object.defineProperty(window, 'location', {
        value: { origin: 'https://rapidly.tech' },
        writable: true,
      })
    }
  })

  it('puts the payload in the URL fragment under /secret/local', () => {
    expect(buildLocalSecretURL('abc')).toBe(
      'https://rapidly.tech/secret/local#abc',
    )
  })

  it('round-trips a real secret end-to-end', () => {
    const secret = 'sk-test-abc123 · multi-line\nsecond line'
    const url = buildLocalSecretURL(toBase64Url(secret))
    const fragment = url.split('#')[1]
    expect(fromBase64Url(fragment)).toBe(secret)
  })
})

describe('encodeLocalSecretEnvelope / decodeLocalSecretEnvelope', () => {
  it('round-trips a v1 envelope with all optional fields', () => {
    const env = {
      v: 1 as const,
      secret: toBase64Url('sk-test-abc'),
      title: 'API Key',
      expires_at: 1234567890000,
      encrypted: false,
    }
    const fragment = encodeLocalSecretEnvelope(env)
    expect(decodeLocalSecretEnvelope(fragment)).toEqual(env)
  })

  it('round-trips a minimal envelope (only v + secret)', () => {
    const env = { v: 1 as const, secret: toBase64Url('hi') }
    expect(decodeLocalSecretEnvelope(encodeLocalSecretEnvelope(env))).toEqual(
      env,
    )
  })

  it('returns null for raw-base64 legacy fragments (no JSON inside)', () => {
    // Legacy links from before envelopes existed: the fragment is
    // the base64url of plaintext, which doesn't decode to valid JSON.
    // Receiver falls back to ``fromBase64Url`` directly.
    const legacy = toBase64Url('plain-secret')
    expect(decodeLocalSecretEnvelope(legacy)).toBeNull()
  })

  it('returns null for malformed base64', () => {
    expect(decodeLocalSecretEnvelope('!!!not-base64!!!')).toBeNull()
  })

  it('returns null when JSON parses but lacks v: 1', () => {
    const noVersion = toBase64Url(JSON.stringify({ secret: 'x' }))
    expect(decodeLocalSecretEnvelope(noVersion)).toBeNull()
  })

  it('returns null when JSON parses but secret is missing', () => {
    const noSecret = toBase64Url(JSON.stringify({ v: 1, title: 'oops' }))
    expect(decodeLocalSecretEnvelope(noSecret)).toBeNull()
  })

  it('preserves the encrypted flag for password-protected payloads', () => {
    const env = {
      v: 1 as const,
      secret: toBase64Url('-----BEGIN PGP MESSAGE-----\n...'),
      encrypted: true,
    }
    const decoded = decodeLocalSecretEnvelope(encodeLocalSecretEnvelope(env))
    expect(decoded?.encrypted).toBe(true)
  })
})
