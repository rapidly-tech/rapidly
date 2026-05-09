'use client'

import Button from '@rapidly-tech/ui/components/forms/Button'
import * as Sentry from '@sentry/nextjs'
import { useEffect } from 'react'

export default function FinanceError({
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
      <h2 className="text-2xl font-medium">Failed to load finance data</h2>
      <p className="max-w-md text-slate-500 dark:text-slate-400">
        We encountered an error loading your financial data. Please try again.
      </p>
      <Button onClick={reset} variant="secondary">
        Try Again
      </Button>
    </div>
  )
}
