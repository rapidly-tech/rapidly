import { afterEach, describe, expect, it } from 'vitest'
import { getOpenInBrowserUrl, isInAppBrowser } from './webview-detection'

describe('isInAppBrowser', () => {
  const originalNavigator = globalThis.navigator

  function mockUA(ua: string) {
    Object.defineProperty(globalThis, 'navigator', {
      value: { userAgent: ua },
      writable: true,
      configurable: true,
    })
  }

  afterEach(() => {
    Object.defineProperty(globalThis, 'navigator', {
      value: originalNavigator,
      writable: true,
      configurable: true,
    })
  })

  it('detects Facebook in-app browser', () => {
    mockUA(
      'Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 FBAN/FB4A FBAV/400.0',
    )
    const result = isInAppBrowser()
    expect(result.detected).toBe(true)
    expect(result.appName).toBe('Facebook')
  })

  it('detects Instagram in-app browser', () => {
    mockUA(
      'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) Instagram 250.0',
    )
    const result = isInAppBrowser()
    expect(result.detected).toBe(true)
    expect(result.appName).toBe('Instagram')
  })

  it('detects TikTok in-app browser', () => {
    mockUA('Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 TikTok 28.0')
    const result = isInAppBrowser()
    expect(result.detected).toBe(true)
    expect(result.appName).toBe('TikTok')
  })

  it('detects Telegram in-app browser', () => {
    mockUA('Mozilla/5.0 (Linux; Android 12) Telegram 9.0')
    const result = isInAppBrowser()
    expect(result.detected).toBe(true)
    expect(result.appName).toBe('Telegram')
  })

  it('detects generic Android WebView', () => {
    mockUA(
      'Mozilla/5.0 (Linux; Android 12; wv) AppleWebKit/537.36 Chrome/100.0',
    )
    const result = isInAppBrowser()
    expect(result.detected).toBe(true)
    expect(result.appName).toBe('Android WebView')
  })

  it('detects Google Search App', () => {
    mockUA('Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 GSA/14.0')
    const result = isInAppBrowser()
    expect(result.detected).toBe(true)
    expect(result.appName).toBe('Google Search App')
  })

  it('returns false for Chrome desktop', () => {
    mockUA(
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    )
    const result = isInAppBrowser()
    expect(result.detected).toBe(false)
    expect(result.appName).toBeNull()
  })

  it('returns false for Safari', () => {
    mockUA(
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15',
    )
    const result = isInAppBrowser()
    expect(result.detected).toBe(false)
    expect(result.appName).toBeNull()
  })

  it('returns false for Firefox', () => {
    mockUA(
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
    )
    const result = isInAppBrowser()
    expect(result.detected).toBe(false)
    expect(result.appName).toBeNull()
  })
})

describe('getOpenInBrowserUrl', () => {
  const originalNavigator = globalThis.navigator

  afterEach(() => {
    Object.defineProperty(globalThis, 'navigator', {
      value: originalNavigator,
      writable: true,
      configurable: true,
    })
  })

  it('generates intent:// URL for Android', () => {
    Object.defineProperty(globalThis, 'navigator', {
      value: { userAgent: 'Mozilla/5.0 (Linux; Android 12)' },
      writable: true,
      configurable: true,
    })
    const url = getOpenInBrowserUrl('https://example.com/share#/d/abc')
    expect(url).toBe(
      'intent://example.com/share#/d/abc#Intent;scheme=https;end',
    )
  })

  it('returns URL as-is for iOS', () => {
    Object.defineProperty(globalThis, 'navigator', {
      value: {
        userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)',
      },
      writable: true,
      configurable: true,
    })
    const url = getOpenInBrowserUrl('https://example.com/share')
    expect(url).toBe('https://example.com/share')
  })
})
