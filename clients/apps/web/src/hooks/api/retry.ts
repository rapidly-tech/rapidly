import {
  ApiResponseError,
  AuthenticationError,
  ResourceNotFoundError,
} from '@rapidly-tech/client'

type ResolvableError =
  | ApiResponseError
  | AuthenticationError
  | ResourceNotFoundError

/**
 * Determines whether a failed query should be retried.
 *
 * Authentication (401), forbidden (403), and not-found (404) errors are
 * terminal -- there is no point in retrying them. Everything else gets
 * up to three attempts before the query is marked as failed.
 */
const shouldRetry = (attempt: number, error: ResolvableError): boolean => {
  // Terminal error classes that will never succeed on retry
  if (
    error instanceof AuthenticationError ||
    error instanceof ResourceNotFoundError
  ) {
    return false
  }

  // Client errors (4xx) are terminal — retrying won't help
  if (error instanceof ApiResponseError) {
    const status = error.response?.status
    if (status && status >= 400 && status < 500) {
      return false
    }
  }

  return attempt <= 2
}

export const baseRetry = shouldRetry
