'use client'

import { JSX } from 'react'

export function ErrorMessage({ message }: { message: string }): JSX.Element {
  return (
    <div
      className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400"
      role="alert"
    >
      <span className="block sm:inline">{message}</span>
    </div>
  )
}
