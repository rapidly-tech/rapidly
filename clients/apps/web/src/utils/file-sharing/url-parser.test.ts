import { describe, expect, it } from 'vitest'

import { isValidSlugFormat, parseHash } from './url-parser'

// 64-char SHA-256 hex digest (arbitrary but realistic).
const SHA256_HEX =
  'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'

describe('isValidSlugFormat', () => {
  it('accepts a minimal lowercase slug', () => {
    expect(isValidSlugFormat('ab')).toBe(true)
  })

  it('accepts slugs with hyphens and forward slashes', () => {
    expect(isValidSlugFormat('abc-123/xyz')).toBe(true)
    expect(isValidSlugFormat('workspace/file-456')).toBe(true)
  })

  it('rejects uppercase letters', () => {
    expect(isValidSlugFormat('Abc')).toBe(false)
    expect(isValidSlugFormat('slug-X')).toBe(false)
  })

  it('rejects empty and one-character slugs', () => {
    expect(isValidSlugFormat('')).toBe(false)
    expect(isValidSlugFormat('a')).toBe(false)
  })

  it('rejects slugs that start with a hyphen or slash', () => {
    expect(isValidSlugFormat('-abc')).toBe(false)
    expect(isValidSlugFormat('/abc')).toBe(false)
  })

  it('rejects slugs with unsupported characters', () => {
    expect(isValidSlugFormat('abc_def')).toBe(false)
    expect(isValidSlugFormat('abc.def')).toBe(false)
    expect(isValidSlugFormat('abc def')).toBe(false)
  })

  it('rejects slugs over 256 chars', () => {
    expect(isValidSlugFormat('a' + 'b'.repeat(255))).toBe(true) // 256 chars = max
    expect(isValidSlugFormat('a' + 'b'.repeat(256))).toBe(false) // 257 chars
  })
})

describe('parseHash — password-only (zero-knowledge)', () => {
  it('decodes a base64 password', () => {
    const encoded = btoa('hunter2')
    const parsed = parseHash(`#/p/${encoded}`)
    expect(parsed).toEqual({ mode: 'password', password: 'hunter2' })
  })

  it('returns null for invalid base64 (falls through to no match)', () => {
    // "!" is not valid base64. parseHash should try the next pattern and
    // ultimately return null since no other pattern matches.
    expect(parseHash('#/p/!!!')).toBeNull()
  })

  it('rejects overly long base64 payloads (>1024 chars)', () => {
    const long = 'A'.repeat(1025)
    expect(parseHash(`#/p/${long}`)).toBeNull()
  })
})

describe('parseHash — secret/file with password', () => {
  it('parses #/s/{uuid}/{password}', () => {
    expect(parseHash('#/s/abc-123/hunter2')).toEqual({
      mode: 'secret',
      type: 's',
      uuid: 'abc-123',
      password: 'hunter2',
    })
  })

  it('parses #/f/{uuid}/{password}', () => {
    expect(parseHash('#/f/xyz-456/pw')).toEqual({
      mode: 'secret',
      type: 'f',
      uuid: 'xyz-456',
      password: 'pw',
    })
  })
})

describe('parseHash — secret/file short link (no password)', () => {
  it('parses #/s/{uuid}', () => {
    expect(parseHash('#/s/abc-123')).toEqual({
      mode: 'secret',
      type: 's',
      uuid: 'abc-123',
    })
  })

  it('parses #/f/{uuid}', () => {
    expect(parseHash('#/f/xyz-456')).toEqual({
      mode: 'secret',
      type: 'f',
      uuid: 'xyz-456',
    })
  })
})

describe('parseHash — file-sharing with key + salt', () => {
  it('parses the full form with key + salt + password', () => {
    const parsed = parseHash(
      `#/d/my-slug/k/base64keyAAA/s/base64saltBBB/p/${SHA256_HEX}`,
    )
    expect(parsed).toEqual({
      mode: 'file-sharing',
      slug: 'my-slug',
      encryptionKey: 'base64keyAAA',
      hkdfSalt: 'base64saltBBB',
      password: SHA256_HEX, // stays lowercase
    })
  })

  it('lowercases uppercase hex in the password segment', () => {
    const upperHex = SHA256_HEX.toUpperCase()
    const parsed = parseHash(
      `#/d/my-slug/k/base64keyAAA/s/base64saltBBB/p/${upperHex}`,
    )
    expect((parsed as { password: string } | null)?.password).toBe(SHA256_HEX)
  })

  it('parses key + salt (no password)', () => {
    expect(parseHash('#/d/my-slug/k/base64keyAAA/s/base64saltBBB')).toEqual({
      mode: 'file-sharing',
      slug: 'my-slug',
      encryptionKey: 'base64keyAAA',
      hkdfSalt: 'base64saltBBB',
    })
  })

  it('rejects a non-hex or wrong-length password segment', () => {
    // 63 chars (one short) — won't match the {64} regex.
    const shortHex = SHA256_HEX.slice(0, 63)
    expect(parseHash(`#/d/my-slug/k/keyAAA/s/saltBBB/p/${shortHex}`)).toBeNull()
  })
})

describe('parseHash — legacy file-sharing (no salt)', () => {
  it('parses legacy key + password (no salt)', () => {
    expect(parseHash(`#/d/my-slug/k/base64keyAAA/p/${SHA256_HEX}`)).toEqual({
      mode: 'file-sharing',
      slug: 'my-slug',
      encryptionKey: 'base64keyAAA',
      password: SHA256_HEX,
    })
  })

  it('parses legacy key-only', () => {
    expect(parseHash('#/d/my-slug/k/base64keyAAA')).toEqual({
      mode: 'file-sharing',
      slug: 'my-slug',
      encryptionKey: 'base64keyAAA',
    })
  })

  it('parses legacy password-only (no key)', () => {
    expect(parseHash(`#/d/my-slug/p/${SHA256_HEX}`)).toEqual({
      mode: 'file-sharing',
      slug: 'my-slug',
      password: SHA256_HEX,
    })
  })

  it('parses the plain legacy form #/d/{slug}', () => {
    expect(parseHash('#/d/my-slug')).toEqual({
      mode: 'file-sharing',
      slug: 'my-slug',
    })
  })

  it('returns null for a slug that violates the SAFE_SLUG pattern', () => {
    expect(parseHash('#/d/UPPERCASE')).toBeNull()
    expect(parseHash('#/d/slug_with_underscore')).toBeNull()
  })
})

describe('parseHash — rejects malformed hashes', () => {
  it.each([
    ['empty string', ''],
    ['bare #', '#'],
    ['no leading slash', '#foo'],
    ['unknown mode', '#/x/slug'],
    ['just #/d/', '#/d/'],
  ])('returns null for %s', (_label, input) => {
    expect(parseHash(input)).toBeNull()
  })
})
