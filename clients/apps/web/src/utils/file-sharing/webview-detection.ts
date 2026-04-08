/**
 * Detect in-app browsers (WebViews) that silently fail on WebRTC and file downloads.
 *
 * WebView browsers from Facebook, Instagram, TikTok, Telegram, etc. use restricted
 * browser engines that lack WebRTC DataChannel support and often block file downloads.
 * This module detects these environments and provides "Open in Browser" URL generation.
 */

// ── UA Pattern Map ──

const WEBVIEW_PATTERNS: Array<{ pattern: RegExp; appName: string }> = [
  { pattern: /FBAN\/|FBAV\//i, appName: 'Facebook' },
  { pattern: /Instagram/i, appName: 'Instagram' },
  { pattern: /Line\//i, appName: 'LINE' },
  { pattern: /\bTwitter\b/i, appName: 'Twitter/X' },
  { pattern: /Snapchat/i, appName: 'Snapchat' },
  { pattern: /; wv\)/i, appName: 'Android WebView' },
  { pattern: /GSA\//i, appName: 'Google Search App' },
  { pattern: /TikTok/i, appName: 'TikTok' },
  { pattern: /Telegram/i, appName: 'Telegram' },
]

// ── Detection ──

/**
 * Check if the current browser is an in-app WebView.
 *
 * Returns the detected app name if in a WebView, or null if not.
 */
export function isInAppBrowser(): {
  detected: boolean
  appName: string | null
} {
  if (typeof navigator === 'undefined') {
    return { detected: false, appName: null }
  }

  const ua = navigator.userAgent
  for (const { pattern, appName } of WEBVIEW_PATTERNS) {
    if (pattern.test(ua)) {
      return { detected: true, appName }
    }
  }

  return { detected: false, appName: null }
}

// ── Open in Browser URL ──

/**
 * Generate a URL that opens the current page in the device's default browser.
 *
 * - Android: Uses `intent://` URI scheme to launch the default browser
 * - iOS: Falls back to the same URL (iOS typically opens Safari from share sheet)
 */
export function getOpenInBrowserUrl(currentUrl: string): string {
  if (typeof navigator === 'undefined') return currentUrl

  const ua = navigator.userAgent
  const isAndroid = /Android/i.test(ua)

  if (isAndroid) {
    // Android intent:// scheme opens the URL in the default browser
    // Strip the protocol to form the intent URI
    const urlWithoutProtocol = currentUrl.replace(/^https?:\/\//, '')
    const scheme = currentUrl.startsWith('https') ? 'https' : 'http'
    return `intent://${urlWithoutProtocol}#Intent;scheme=${scheme};end`
  }

  // iOS and other platforms: return the URL as-is
  // Users will need to use the share sheet or copy-paste
  return currentUrl
}
