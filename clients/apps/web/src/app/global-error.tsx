'use client'
import * as Sentry from '@sentry/nextjs'
import { useEffect } from 'react'

import Button from '@rapidly-tech/ui/components/forms/Button'

/** Top-level error boundary that renders a full-page fallback when an unrecoverable error occurs. */
export default function GlobalError({ error }: { error: Error }) {
  useEffect(() => {
    Sentry.captureException(error)
  }, [error])

  return (
    <html lang="en">
      <body className="bg-slate-200 dark:bg-slate-900">
        <div className="flex grow flex-col items-center justify-center space-y-4 p-16">
          <h2 className="text-xl text-slate-900 dark:text-slate-100">
            Something went wrong!
          </h2>

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
      </body>
    </html>
  )
}
