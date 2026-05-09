'use client'

import Button from '@rapidly-tech/ui/components/forms/Button'
import * as Sentry from '@sentry/nextjs'
import { useEffect } from 'react'

/** Application-level error boundary displayed when a page throws an unexpected error. */
export default function Error({ error }: { error: Error }) {
  useEffect(() => {
    Sentry.captureException(error)
  }, [error])

  return (
    <div className="flex grow flex-col items-center justify-center space-y-4 p-16">
      <h2 className="text-xl">Something went wrong!</h2>

      <Button
        fullWidth={false}
        onClick={() => {
          window.location.href = '/'
        }}
      >
        <span>Go back to Rapidly</span>
      </Button>

      <pre className="mt-24 text-sm whitespace-break-spaces text-slate-400 dark:text-slate-500">
        An error has been reported automatically.
      </pre>
    </div>
  )
}
