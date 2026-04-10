import React from 'react'
import { twMerge } from 'tailwind-merge'

type Color = 'default' | 'muted' | 'red' | 'green' | 'info'

const Banner = ({
  children,
  right,
  color,
}: {
  children: React.ReactNode
  right?: React.ReactNode
  color: Color
}) => {
  return (
    <div
      className={twMerge(
        'flex items-center justify-between gap-2 rounded-2xl px-3 py-2 text-sm backdrop-blur-2xl backdrop-saturate-150',
        color === 'default'
          ? 'border border-white/8 bg-white/5 shadow-sm dark:border-white/6 dark:bg-white/3'
          : '',
        color === 'muted'
          ? 'border border-white/6 bg-white/3 text-slate-500 dark:border-white/4 dark:bg-white/2 dark:text-slate-400'
          : '',
        color === 'red'
          ? 'border border-red-300/15 bg-red-500/6 text-red-600 dark:border-red-500/10 dark:bg-red-500/4 dark:text-red-400'
          : '',
        color === 'green'
          ? 'border border-emerald-300/15 bg-emerald-500/6 text-emerald-600 dark:border-emerald-500/10 dark:bg-emerald-500/4 dark:text-emerald-300'
          : '',
        color === 'info'
          ? 'border border-slate-300/15 bg-slate-500/6 text-slate-600 dark:border-slate-500/10 dark:bg-slate-500/4 dark:text-slate-300'
          : '',
      )}
    >
      <div className="flex flex-1 items-center gap-2">{children}</div>
      {right && <div>{right}</div>}
    </div>
  )
}

export default Banner
