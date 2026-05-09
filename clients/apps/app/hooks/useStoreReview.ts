/**
 * Store review prompt management for the Rapidly mobile app.
 *
 * Follows Apple guidelines: maximum 3 prompts per 365-day window,
 * at least 120 days between prompts. The review dialog is only surfaced
 * after the user has placed orders and opened the app at least 5 times.
 */
import * as StoreReview from 'expo-store-review'
import { useCallback, useEffect, useState } from 'react'
import {
  getStorageItemAsync,
  setStorageItemAsync,
  useStorageState,
} from './storage'

const KEYS = {
  HAS_RATED: 'rating_prompt_has_rated',
  APP_OPENS: 'rating_prompt_app_open_count',
  LAST_SHOWN: 'rating_prompt_last_shown',
  PROMPT_COUNT: 'rating_prompt_ask_count',
} as const

const MIN_APP_OPENS = 5
const MAX_YEARLY_PROMPTS = 3
const MIN_DAYS_GAP = 120

export interface UseStoreReviewReturn {
  requestReview: () => Promise<void>
  shouldShow: (hasOrders: boolean) => boolean
  isLoading: boolean
  incrementAppOpenCount: () => Promise<void>
}

/** Parses a storage string to an integer with a fallback. */
function parseIntSafe(str: string | null, fallback = 0): number {
  return str ? parseInt(str, 10) : fallback
}

/** Checks whether enough days have elapsed since a stored timestamp. */
function daysSinceTimestamp(epochStr: string | null): number {
  if (!epochStr) return Infinity
  const then = new Date(parseInt(epochStr, 10))
  return Math.floor((Date.now() - then.getTime()) / (1000 * 60 * 60 * 24))
}

export function useStoreReview(): UseStoreReviewReturn {
  const [[loadingRated, hasRated]] = useStorageState(KEYS.HAS_RATED)
  const [[loadingOpens, appOpens]] = useStorageState(KEYS.APP_OPENS)
  const [[loadingLast, lastShown]] = useStorageState(KEYS.LAST_SHOWN)
  const [[loadingCount, promptCount]] = useStorageState(KEYS.PROMPT_COUNT)

  const [available, setAvailable] = useState(false)
  const isLoading = loadingRated || loadingOpens || loadingLast || loadingCount

  useEffect(() => {
    StoreReview.isAvailableAsync().then(setAvailable)
  }, [])

  const shouldShow = useCallback(
    (hasOrders: boolean) => {
      if (isLoading || !available) return false

      const opens = parseIntSafe(appOpens)
      const meetsUsage = opens >= MIN_APP_OPENS && hasOrders

      const notRated = hasRated !== 'true'
      const count = parseIntSafe(promptCount)
      const belowCap = count < MAX_YEARLY_PROMPTS
      const enoughTime = daysSinceTimestamp(lastShown) >= MIN_DAYS_GAP

      return meetsUsage && notRated && belowCap && enoughTime
    },
    [isLoading, available, hasRated, appOpens, promptCount, lastShown],
  )

  const requestReview = useCallback(async () => {
    if (!available || hasRated === 'true') return

    const count = parseIntSafe(promptCount)
    if (count >= MAX_YEARLY_PROMPTS) return
    if (daysSinceTimestamp(lastShown) < MIN_DAYS_GAP) return

    await StoreReview.requestReview()
    await setStorageItemAsync(KEYS.LAST_SHOWN, Date.now().toString())
    await setStorageItemAsync(KEYS.PROMPT_COUNT, (count + 1).toString())
    await setStorageItemAsync(KEYS.HAS_RATED, 'true')
  }, [available, hasRated, promptCount, lastShown])

  const incrementAppOpenCount = useCallback(async () => {
    const stored = await getStorageItemAsync(KEYS.APP_OPENS)
    const current = parseIntSafe(stored)
    await setStorageItemAsync(KEYS.APP_OPENS, (current + 1).toString())
  }, [])

  return { requestReview, shouldShow, isLoading, incrementAppOpenCount }
}
