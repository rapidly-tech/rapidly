'use client'

/**
 * React hook over the ``utils/collab/display-name`` helpers.
 *
 * Reads from ``localStorage`` once on mount; writes on every change
 * so a returning user sees their name pre-filled. Tolerates SSR +
 * disabled-storage environments by falling back to in-memory state.
 */

import { useCallback, useEffect, useState } from 'react'

import {
  readStoredDisplayName,
  writeStoredDisplayName,
} from '@/utils/collab/display-name'

export function useDisplayName(): [string, (next: string) => void] {
  // Start blank so SSR hydration is stable; useEffect below replaces
  // with the persisted value on first client paint.
  const [name, setName] = useState('')

  useEffect(() => {
    setName(readStoredDisplayName())
  }, [])

  const set = useCallback((next: string) => {
    setName(next)
    writeStoredDisplayName(next)
  }, [])

  return [name, set]
}
