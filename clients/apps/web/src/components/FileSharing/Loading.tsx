'use client'

import { JSX } from 'react'

export default function Loading({ text }: { text?: string }): JSX.Element {
  return (
    <div
      className="flex flex-col items-center"
      role="status"
      aria-live="polite"
    >
      <div className="mb-4 h-8 w-8 animate-spin rounded-full border-b-2 border-slate-500 dark:border-slate-400"></div>
      {text ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">{text}</p>
      ) : (
        <span className="sr-only">Loading</span>
      )}
    </div>
  )
}
