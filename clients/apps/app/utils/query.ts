/**
 * Shared TanStack Query client configuration for the Rapidly mobile app.
 *
 * Sets sensible defaults for stale time, garbage collection, and retry
 * behaviour. Validation errors and 4xx responses are never retried.
 */
export { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ApiResponseError, isValidationError } from '@rapidly-tech/client'
import { QueryClient } from '@tanstack/react-query'

const MAX_RETRIES = 3
const STALE_TIME_MS = 60 * 1000
const GC_TIME_MS = 1000 * 60 * 60 // 1 hour

/** Determines whether a failed query should be retried. */
function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  // Never retry client errors (auth, validation, not found, etc.)
  if (
    error instanceof ApiResponseError &&
    error.response.status > 400 &&
    error.response.status < 500
  ) {
    return false
  }

  if (isValidationError(error)) return false
  if (failureCount >= MAX_RETRIES) return false

  return true
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: STALE_TIME_MS,
      gcTime: GC_TIME_MS,
      throwOnError: true,
      retry: shouldRetryQuery,
    },
  },
})
