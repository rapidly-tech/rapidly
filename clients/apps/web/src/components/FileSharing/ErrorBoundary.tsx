'use client'

import * as Sentry from '@sentry/nextjs'
import React, { Component, ReactNode } from 'react'
import { WarningIcon } from './Icons'
import ReturnHome from './ReturnHome'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
}

/**
 * Error boundary for file sharing components.
 *
 * Catches unhandled errors in Uploader/Downloader component trees
 * and shows a recovery UI instead of crashing the entire page.
 */
export class FileSharingErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    Sentry.captureException(error, {
      extra: { componentStack: errorInfo.componentStack },
    })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="w-full max-w-md text-center">
          <div className="mb-4 inline-flex h-16 w-16 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/30">
            <WarningIcon className="h-8 w-8 text-red-500" />
          </div>
          <h2 className="rp-text-primary mb-2 text-xl font-bold">
            Something went wrong
          </h2>
          <p className="mb-6 text-slate-500 dark:text-slate-400">
            An unexpected error occurred. Please try again.
          </p>
          <div className="flex justify-center gap-3">
            <button
              type="button"
              className="rounded-xl bg-slate-600 px-6 py-3 text-sm font-medium text-white transition-colors duration-200 hover:bg-slate-700 dark:bg-slate-500 dark:hover:bg-slate-400"
              onClick={() => window.location.reload()}
            >
              Try Again
            </button>
            <ReturnHome />
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
