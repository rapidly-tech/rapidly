'use client'

import { JSX } from 'react'

function getTypeColor(fileType: string): string {
  if (fileType.startsWith('image/'))
    return 'bg-slate-200 dark:bg-slate-800/30 text-slate-700 dark:text-slate-300'
  if (fileType.startsWith('text/'))
    return 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300'
  if (fileType.startsWith('audio/'))
    return 'bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300'
  if (fileType.startsWith('video/'))
    return 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300'
  return 'bg-surface text-slate-700 dark:text-slate-300'
}

export default function TypeBadge({ type }: { type: string }): JSX.Element {
  return (
    <div
      className={`rounded-md px-2 py-0.5 text-[10px] font-medium ${getTypeColor(
        type,
      )} transition-all duration-300`}
    >
      {type || 'unknown'}
    </div>
  )
}
