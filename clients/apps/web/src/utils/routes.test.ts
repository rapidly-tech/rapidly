import { describe, expect, it } from 'vitest'

import { ROUTES } from './routes'

describe('ROUTES — top-level paths', () => {
  it('exposes the canonical public paths', () => {
    expect(ROUTES.HOME).toBe('/')
    expect(ROUTES.LOGIN).toBe('/login')
    expect(ROUTES.VERIFY_EMAIL).toBe('/verify-email')
    expect(ROUTES.START).toBe('/start')
  })
})

describe('ROUTES.DASHBOARD', () => {
  it('exposes static dashboard paths', () => {
    expect(ROUTES.DASHBOARD.ROOT).toBe('/dashboard')
    expect(ROUTES.DASHBOARD.ACCOUNT).toBe('/dashboard/account')
    expect(ROUTES.DASHBOARD.ACCOUNT_PREFERENCES).toBe(
      '/dashboard/account/preferences',
    )
  })

  it('builds per-workspace org paths', () => {
    expect(ROUTES.DASHBOARD.org('acme')).toBe('/dashboard/acme')
    expect(ROUTES.DASHBOARD.org('my-team')).toBe('/dashboard/my-team')
  })

  it('builds per-workspace send-files path', () => {
    expect(ROUTES.DASHBOARD.files.new('acme')).toBe(
      '/dashboard/acme/shares/send-files',
    )
  })

  it('builds settings + developers-anchor paths', () => {
    expect(ROUTES.DASHBOARD.settings('acme')).toBe('/dashboard/acme/settings')
    expect(ROUTES.DASHBOARD.settingsDevelopers('acme')).toBe(
      '/dashboard/acme/settings#developers',
    )
  })

  it('builds finance account path', () => {
    expect(ROUTES.DASHBOARD.finance.account('acme')).toBe(
      '/dashboard/acme/finance/account',
    )
  })
})

describe('ROUTES.PORTAL', () => {
  it('builds portal root / request / settings paths', () => {
    expect(ROUTES.PORTAL.root('acme')).toBe('/acme/portal')
    expect(ROUTES.PORTAL.request('acme')).toBe('/acme/portal/request')
    expect(ROUTES.PORTAL.settings('acme')).toBe('/acme/portal/settings')
  })
})

describe('ROUTES — slug pass-through', () => {
  it('does not URL-encode the slug (builders delegate encoding to callers)', () => {
    // The builders are plain string interpolation — callers must pre-
    // encode any unsafe slug segments. This test pins that expectation
    // so any future "helpful" encoding behaviour is flagged.
    expect(ROUTES.DASHBOARD.org('a b c')).toBe('/dashboard/a b c')
    expect(ROUTES.DASHBOARD.org('weird/slug')).toBe('/dashboard/weird/slug')
  })
})
