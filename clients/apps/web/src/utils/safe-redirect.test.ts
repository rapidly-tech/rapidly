import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { ALLOWED_STRIPE_ORIGINS, isSafeRedirect } from './safe-redirect'

function stubOrigin(origin: string) {
  Object.defineProperty(window, 'location', {
    value: { origin, href: origin + '/' },
    writable: true,
    configurable: true,
  })
}

describe('isSafeRedirect', () => {
  let originalLocation: unknown

  beforeEach(() => {
    originalLocation = window.location
    stubOrigin('https://app.rapidly.tech')
  })

  afterEach(() => {
    Object.defineProperty(window, 'location', {
      value: originalLocation,
      writable: true,
      configurable: true,
    })
  })

  it('accepts a relative URL (same origin by default)', () => {
    expect(isSafeRedirect('/dashboard')).toBe(true)
    expect(isSafeRedirect('/dashboard/some/slug?q=1#hash')).toBe(true)
  })

  it('accepts an absolute URL on the same origin', () => {
    expect(isSafeRedirect('https://app.rapidly.tech/dashboard')).toBe(true)
  })

  it('rejects a different origin when no allowlist is passed', () => {
    expect(isSafeRedirect('https://evil.example/path')).toBe(false)
    expect(isSafeRedirect('https://rapidly.tech')).toBe(false) // different origin — www vs app
  })

  it('accepts an external origin when explicitly allow-listed', () => {
    expect(
      isSafeRedirect('https://checkout.stripe.com/pay/abc', [
        'https://checkout.stripe.com',
      ]),
    ).toBe(true)
  })

  it('rejects an external origin that is not on the allowlist', () => {
    expect(
      isSafeRedirect('https://malicious.stripe.com.evil/path', [
        'https://checkout.stripe.com',
      ]),
    ).toBe(false)
  })

  it('accepts every ALLOWED_STRIPE_ORIGINS entry when passed', () => {
    for (const origin of ALLOWED_STRIPE_ORIGINS) {
      expect(isSafeRedirect(`${origin}/path`, ALLOWED_STRIPE_ORIGINS)).toBe(
        true,
      )
    }
  })

  it('exposes the expected Stripe allowlist', () => {
    expect(ALLOWED_STRIPE_ORIGINS).toEqual([
      'https://connect.stripe.com',
      'https://checkout.stripe.com',
      'https://dashboard.stripe.com',
    ])
  })

  it('rejects javascript: URLs (origin is "null")', () => {
    expect(isSafeRedirect('javascript:alert(1)')).toBe(false)
    expect(isSafeRedirect('JavaScript:alert(1)')).toBe(false)
  })

  it('rejects data: URLs', () => {
    expect(isSafeRedirect('data:text/html,<script>alert(1)</script>')).toBe(
      false,
    )
  })

  it('rejects malformed URLs gracefully (returns false, no throw)', () => {
    // The URL constructor throws on some inputs; isSafeRedirect catches and
    // returns false rather than propagating.
    expect(() => isSafeRedirect('ht!tp:bad')).not.toThrow()
    expect(isSafeRedirect('http://[::bad]')).toBe(false)
  })

  it('protocol-relative URLs resolve against window.location — different host = rejected', () => {
    // "//evil.example/path" becomes "https://evil.example/path" under the
    // current origin's protocol — a classic open-redirect bypass attempt
    // that the check must still reject.
    expect(isSafeRedirect('//evil.example/path')).toBe(false)
  })
})
