'use client'

import {
  getOpenInBrowserUrl,
  isInAppBrowser,
} from '@/utils/file-sharing/webview-detection'
import Button from '@rapidly-tech/ui/components/forms/Button'
import { JSX, useMemo } from 'react'
import { WarningBanner } from './WarningBanner'

/**
 * Warning banner shown when the user is in an in-app browser (WebView).
 *
 * WebView browsers from Facebook, Instagram, TikTok, etc. silently fail
 * on WebRTC and file downloads. This warns the user and provides a button
 * to open the page in their default browser.
 *
 * Non-blocking: warns but does not prevent interaction.
 */
export function WebViewWarning(): JSX.Element | null {
  const detection = useMemo(() => isInAppBrowser(), [])

  if (!detection.detected) return null

  const openUrl = getOpenInBrowserUrl(window.location.href)
  const isAndroid = /Android/i.test(navigator.userAgent)

  return (
    <div className="flex w-full flex-col gap-3">
      <WarningBanner>
        {detection.appName
          ? `${detection.appName}'s built-in browser may not support file transfers.`
          : 'In-app browsers may not support file transfers.'}{' '}
        For the best experience, open this page in your default browser.
      </WarningBanner>
      {isAndroid ? (
        <a href={openUrl} className="w-full">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="w-full"
          >
            Open in Browser
          </Button>
        </a>
      ) : (
        <p className="text-center text-xs text-slate-500 dark:text-slate-400">
          Tap the share button and choose &ldquo;Open in Safari&rdquo; or
          &ldquo;Open in Browser&rdquo;
        </p>
      )}
    </div>
  )
}
