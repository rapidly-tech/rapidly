'use client'

import Button from '@rapidly-tech/ui/components/forms/Button'
import * as Sentry from '@sentry/nextjs'
import { useEffect } from 'react'

/** Error boundary for the landing page section with retry and go-home actions. */
export default function LandingError({
  error,
  reset,
}: {
  error: Error
  reset: () => void
}) {
  useEffect(() => {
    Sentry.captureException(error)
  }, [error])

  return (
    <div className="flex grow flex-col items-center justify-center space-y-6 p-16 text-center">
      <h2 className="text-2xl font-medium">Something went wrong</h2>
      <p className="max-w-md text-slate-500 dark:text-slate-400">
        We encountered an unexpected error loading this page. Please try again.
      </p>
      <div className="flex gap-4">
        <Button onClick={reset} variant="secondary">
          Try Again
        </Button>
        <Button
          onClick={() => {
            window.location.href = '/'
          }}
        >
          Go Home
        </Button>
      </div>
    </div>
  )
}
