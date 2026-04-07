'use client'

import { LocalStorageKey } from '@/hooks/upsell'
import { Icon } from '@iconify/react'
import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = LocalStorageKey.IOS_APP_BANNER_DISMISSED
const DISMISSED_VALUE = 'true'

const isBrowser = (): boolean => typeof window !== 'undefined'

const readDismissedState = (): boolean => {
  if (!isBrowser()) return false
  return localStorage.getItem(STORAGE_KEY) === DISMISSED_VALUE
}

const persistDismissal = (): void => {
  if (!isBrowser()) return
  localStorage.setItem(STORAGE_KEY, DISMISSED_VALUE)
}

const CONTAINER_CLASSES =
  'dark:bg-slate-950 dark:border-slate-900 relative flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-6 pt-8 text-sm md:hidden'

const DISMISS_BTN_CLASSES =
  'dark:text-slate-500 dark:hover:text-slate-500 absolute top-4 right-4 cursor-pointer text-slate-400 transition-colors hover:text-slate-600'

export const IOSAppBanner = () => {
  const [isDismissed, setIsDismissed] = useState(readDismissedState)

  useEffect(() => {
    setIsDismissed(readDismissedState())
  }, [])

  const dismiss = useCallback(() => {
    persistDismissal()
    setIsDismissed(true)
  }, [])

  if (isDismissed) return null

  return (
    <div className={CONTAINER_CLASSES}>
      <button
        type="button"
        onClick={dismiss}
        className={DISMISS_BTN_CLASSES}
        aria-label="Dismiss"
      >
        <Icon icon="solar:close-circle-linear" className="h-4 w-4" />
      </button>

      <div className="flex flex-col gap-1">
        <span className="font-medium">
          Rapidly is coming soon to the App Store
        </span>
        <span className="text-slate-500 dark:text-slate-400">
          Your dashboard, always in your pocket. Get push notifications for new
          file shares and downloads.
        </span>
      </div>
    </div>
  )
}
