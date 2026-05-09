import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { hasConsentCookie, setConsentCookie } from './cookie-consent'

/** Clear every cookie jsdom has stashed between tests so state doesn't
 *  bleed across cases. ``document.cookie`` in jsdom is persistent across
 *  assignments within a single test file unless we explicitly expire
 *  every entry. */
function clearAllCookies() {
  for (const c of document.cookie.split(';')) {
    const name = c.split('=')[0]?.trim()
    if (!name) continue
    document.cookie = `${name}=; path=/; max-age=0`
  }
}

describe('cookie-consent', () => {
  beforeEach(() => {
    clearAllCookies()
  })

  afterEach(() => {
    clearAllCookies()
  })

  describe('hasConsentCookie', () => {
    it('returns false when no consent cookie is set', () => {
      expect(hasConsentCookie()).toBe(false)
    })

    it('returns true after setConsentCookie("accepted")', () => {
      setConsentCookie('accepted')
      expect(hasConsentCookie()).toBe(true)
    })

    it('returns true after setConsentCookie("declined")', () => {
      setConsentCookie('declined')
      expect(hasConsentCookie()).toBe(true)
    })

    it('ignores look-alike cookies', () => {
      // A name that shares a prefix but isn't the consent cookie must
      // not register as consent. ``rapidly_cookie_consent_other=1``
      // starts with ``rapidly_cookie_consent`` but isn't the exact name.
      document.cookie = 'rapidly_cookie_consent_other=foo; path=/'
      expect(hasConsentCookie()).toBe(false)
    })

    it('finds the cookie regardless of ordering in document.cookie', () => {
      document.cookie = 'other=1; path=/'
      setConsentCookie('accepted')
      document.cookie = 'another=2; path=/'
      expect(hasConsentCookie()).toBe(true)
    })
  })

  describe('setConsentCookie', () => {
    it('writes the cookie with the supplied value', () => {
      setConsentCookie('accepted')
      expect(document.cookie).toContain('rapidly_cookie_consent=accepted')
    })

    it('writes declined when supplied', () => {
      setConsentCookie('declined')
      expect(document.cookie).toContain('rapidly_cookie_consent=declined')
    })

    it('overwrites the previous value when called again', () => {
      setConsentCookie('accepted')
      setConsentCookie('declined')
      expect(document.cookie).toContain('rapidly_cookie_consent=declined')
      expect(document.cookie).not.toContain('rapidly_cookie_consent=accepted')
    })
  })
})
