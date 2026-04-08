import { useCallback, useEffect, useRef } from 'react'

/**
 * Returns a debounced version of the given callback.
 * The callback is delayed by `delay` ms and resets on each call.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const useDebouncedCallback = <T extends (...args: any[]) => any>(
  callback: T,
  delay: number,
  dependencies?: unknown[],
) => {
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined)

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current)
      }
    }
  }, [])

  return useCallback(
    (...args: Parameters<T>): void => {
      if (timerRef.current != null) {
        clearTimeout(timerRef.current)
      }
      timerRef.current = setTimeout(() => callback(...args), delay)
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [callback, delay, ...(dependencies ?? [])],
  )
}
