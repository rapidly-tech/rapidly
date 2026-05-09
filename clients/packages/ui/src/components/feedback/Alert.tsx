import type { PropsWithChildren } from 'react'
import { twMerge } from 'tailwind-merge'

interface AlertProps {
  color: 'info' | 'gray' | 'red' | 'green'
}

// Mapping from semantic colour to Tailwind class bundles
const COLOR_MAP: Record<AlertProps['color'], string> = {
  info: 'border-slate-300/15 bg-slate-500/6 text-slate-600 backdrop-blur-2xl backdrop-saturate-150 dark:border-slate-500/10 dark:bg-slate-500/4 dark:text-slate-400',
  gray: 'border-white/8 bg-white/4 text-slate-600 backdrop-blur-2xl backdrop-saturate-150 dark:border-white/6 dark:bg-white/3 dark:text-slate-400',
  red: 'border-red-300/15 bg-red-500/6 text-red-600 backdrop-blur-2xl backdrop-saturate-150 dark:border-red-500/10 dark:bg-red-500/4 dark:text-red-400',
  green:
    'border-emerald-300/15 bg-emerald-500/6 text-emerald-600 backdrop-blur-2xl backdrop-saturate-150 dark:border-emerald-500/10 dark:bg-emerald-500/4 dark:text-emerald-400',
}

/** Colour-coded inline alert for status messages and notices. */
const Alert: React.FC<PropsWithChildren<AlertProps>> = ({
  children,
  color,
}) => (
  <div className={twMerge('rounded-2xl border p-2', COLOR_MAP[color])}>
    {children}
  </div>
)

export default Alert
