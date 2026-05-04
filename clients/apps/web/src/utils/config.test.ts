import { describe, expect, it } from 'vitest'

import { CONFIG, orgOgImageUrl } from './config'

/** ``config.ts`` resolves env vars at module-load time into the frozen
 *  ``CONFIG`` object + a single pure URL builder. Tests focus on:
 *  - CONFIG shape (keys exist + have the right types)
 *  - ``orgOgImageUrl`` as a pure function of ``FRONTEND_BASE_URL`` +
 *    the slug arg
 *  - ``IS_SANDBOX`` staying coherent with ``ENVIRONMENT``
 *  - Derived URLs pointing at paths inside ``FRONTEND_BASE_URL``
 *
 *  Avoiding specific hostname assertions keeps the suite stable across
 *  local / CI / preview environments where NEXT_PUBLIC_FRONTEND_BASE_URL
 *  varies. */

describe('CONFIG — shape', () => {
  it('exposes the documented top-level keys', () => {
    const keys = [
      'ENVIRONMENT',
      'FRONTEND_BASE_URL',
      'BASE_URL',
      'AUTH_COOKIE_KEY',
      'AUTH_MCP_COOKIE_KEY',
      'LOGIN_PATH',
      'POSTHOG_TOKEN',
      'APPLE_DOMAIN_ASSOCIATION',
      'ADMIN_EMAIL',
      'REVOLVER_LANDING_ENABLED',
      'IS_SANDBOX',
      'SANDBOX_URL',
      'OG_IMAGE_URL',
      'OG_POSTS_IMAGE_BASE_URL',
      'SITEMAP_URL',
      'DOCS_BASE_URL',
      'LEGAL_TERMS_URL',
      'LEGAL_PRIVACY_URL',
      'POSTHOG_HOST',
      'DISCORD_WEBHOOK_URL_PREFIX',
    ]
    for (const k of keys) {
      expect(CONFIG).toHaveProperty(k)
    }
  })

  it('uses string types for text-like settings', () => {
    expect(typeof CONFIG.ENVIRONMENT).toBe('string')
    expect(typeof CONFIG.FRONTEND_BASE_URL).toBe('string')
    expect(typeof CONFIG.BASE_URL).toBe('string')
    expect(typeof CONFIG.AUTH_COOKIE_KEY).toBe('string')
    expect(typeof CONFIG.LOGIN_PATH).toBe('string')
  })

  it('REVOLVER_LANDING_ENABLED is a boolean (explicit opt-in flag)', () => {
    expect(typeof CONFIG.REVOLVER_LANDING_ENABLED).toBe('boolean')
  })

  it('IS_SANDBOX stays coherent with ENVIRONMENT', () => {
    // The derived flag is ``ENVIRONMENT === 'sandbox'`` — the two
    // values must never drift apart.
    expect(CONFIG.IS_SANDBOX).toBe(CONFIG.ENVIRONMENT === 'sandbox')
  })
})

describe('CONFIG — defaults', () => {
  // These defaults fire only when the corresponding env var is absent;
  // since the test env may or may not set them, assert the sentinel
  // values show up where configured-but-unset paths hit fallback.

  it('provides a non-empty AUTH_COOKIE_KEY default', () => {
    expect(CONFIG.AUTH_COOKIE_KEY.length).toBeGreaterThan(0)
  })

  it('provides a non-empty AUTH_MCP_COOKIE_KEY default', () => {
    expect(CONFIG.AUTH_MCP_COOKIE_KEY.length).toBeGreaterThan(0)
  })

  it('LOGIN_PATH defaults to a leading-slash path', () => {
    expect(CONFIG.LOGIN_PATH.startsWith('/')).toBe(true)
  })

  it('POSTHOG_HOST is pinned to the US ingestion host', () => {
    // Not env-overridable in config.ts — hard-coded constant.
    expect(CONFIG.POSTHOG_HOST).toBe('https://us.i.posthog.com')
  })

  it('DISCORD_WEBHOOK_URL_PREFIX is pinned to the Discord webhook API', () => {
    expect(CONFIG.DISCORD_WEBHOOK_URL_PREFIX).toBe(
      'https://discord.com/api/webhooks',
    )
  })
})

describe('CONFIG — derived URLs', () => {
  it('OG_IMAGE_URL is the brand OG asset under FRONTEND_BASE_URL', () => {
    expect(CONFIG.OG_IMAGE_URL).toBe(
      `${CONFIG.FRONTEND_BASE_URL}/assets/brand/rapidly_og.jpg`,
    )
  })

  it('OG_POSTS_IMAGE_BASE_URL is the posts OG prefix under FRONTEND_BASE_URL', () => {
    expect(CONFIG.OG_POSTS_IMAGE_BASE_URL).toBe(
      `${CONFIG.FRONTEND_BASE_URL}/assets/posts/og`,
    )
  })

  it('SITEMAP_URL sits at /sitemap.xml under FRONTEND_BASE_URL', () => {
    expect(CONFIG.SITEMAP_URL).toBe(`${CONFIG.FRONTEND_BASE_URL}/sitemap.xml`)
  })

  it('LEGAL_TERMS_URL and LEGAL_PRIVACY_URL sit under /legal', () => {
    expect(CONFIG.LEGAL_TERMS_URL).toBe(
      `${CONFIG.FRONTEND_BASE_URL}/legal/terms`,
    )
    expect(CONFIG.LEGAL_PRIVACY_URL).toBe(
      `${CONFIG.FRONTEND_BASE_URL}/legal/privacy`,
    )
  })

  it('DOCS_BASE_URL is an https URL', () => {
    expect(CONFIG.DOCS_BASE_URL.startsWith('https://')).toBe(true)
  })
})

describe('orgOgImageUrl', () => {
  it('returns the OG image endpoint with the slug as a query param', () => {
    expect(orgOgImageUrl('acme')).toBe(
      `${CONFIG.FRONTEND_BASE_URL}/og?org=acme`,
    )
  })

  it('passes the slug through verbatim (no URL-encoding)', () => {
    // Pass-through is the documented contract; any future URL-encoding
    // would change the result for "/" and " " characters.
    expect(orgOgImageUrl('a b')).toBe(`${CONFIG.FRONTEND_BASE_URL}/og?org=a b`)
    expect(orgOgImageUrl('weird/slug')).toBe(
      `${CONFIG.FRONTEND_BASE_URL}/og?org=weird/slug`,
    )
  })

  it('handles empty slug without throwing', () => {
    expect(orgOgImageUrl('')).toBe(`${CONFIG.FRONTEND_BASE_URL}/og?org=`)
  })
})
