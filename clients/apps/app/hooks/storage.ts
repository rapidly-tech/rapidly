/**
 * Cross-platform secure storage utilities for the Rapidly mobile app.
 *
 * Uses expo-secure-store on native platforms and falls back to
 * localStorage on web. The useStorageState hook provides a reactive
 * state tuple that auto-persists writes.
 */
import * as SecureStore from 'expo-secure-store'
import { useCallback, useEffect, useReducer } from 'react'
import { Platform } from 'react-native'

type StateEntry<T> = [boolean, T | null]
type UseStateHook<T> = [StateEntry<T>, (value: T | null) => void]

function useAsyncState<T>(
  initial: StateEntry<T> = [true, null],
): UseStateHook<T> {
  return useReducer(
    (_prev: StateEntry<T>, next: T | null = null): StateEntry<T> => [
      false,
      next,
    ],
    initial,
  ) as UseStateHook<T>
}

/** Read a value from platform storage. */
export async function getStorageItemAsync(key: string): Promise<string | null> {
  return await SecureStore.getItemAsync(key)
}

/** Write or remove a value in platform storage. */
export async function setStorageItemAsync(
  key: string,
  value: string | null,
): Promise<void> {
  if (Platform.OS === 'web') {
    try {
      if (value === null) {
        localStorage.removeItem(key)
      } else {
        localStorage.setItem(key, value)
      }
    } catch (e) {
      console.error('Local storage is unavailable:', e)
    }
    return
  }

  if (value == null) {
    await SecureStore.deleteItemAsync(key)
  } else {
    await SecureStore.setItemAsync(key, value)
  }
}

/**
 * Reactive hook wrapping a single persisted string value.
 *
 * Returns a [[isLoading, value], setValue] tuple. Reads happen once on
 * mount; writes are persisted asynchronously.
 */
export function useStorageState(key: string): UseStateHook<string> {
  const [state, setState] = useAsyncState<string>()

  // Hydrate from storage on mount
  useEffect(() => {
    if (Platform.OS === 'web') {
      try {
        if (typeof localStorage !== 'undefined') {
          setState(localStorage.getItem(key))
        }
      } catch (e) {
        console.error('Local storage is unavailable:', e)
      }
    } else {
      SecureStore.getItemAsync(key).then((v) => setState(v))
    }
  }, [key])

  // Setter that updates both React state and persistent storage
  const setValue = useCallback(
    (next: string | null) => {
      setState(next)
      setStorageItemAsync(key, next)
    },
    [key],
  )

  return [state, setValue]
}
