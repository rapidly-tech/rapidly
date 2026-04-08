/**
 * Tracks cold-start app opens for store review prompt eligibility.
 *
 * Increments a persistent counter exactly once per component lifecycle
 * (guarded by a ref to prevent double-counting in StrictMode).
 */
import { useEffect, useRef } from 'react'
import { useStoreReview } from './useStoreReview'

export function useAppOpenTracking() {
  const { incrementAppOpenCount } = useStoreReview()
  const counted = useRef(false)

  useEffect(() => {
    if (!counted.current) {
      incrementAppOpenCount()
      counted.current = true
    }
  }, [incrementAppOpenCount])
}
