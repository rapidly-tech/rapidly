'use client'

import { JSX, ReactNode } from 'react'
import { WarningIcon } from './Icons'

export function WarningBanner({
  children,
  icon,
}: {
  children: ReactNode
  icon?: ReactNode
}): JSX.Element {
  return (
    <div className="flex w-full items-center gap-x-2 rounded-lg bg-amber-50 px-4 py-3 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400">
      {icon ?? <WarningIcon className="h-5 w-5 shrink-0" />}
      <span className="text-sm">{children}</span>
    </div>
  )
}
