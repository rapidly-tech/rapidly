import { twMerge } from 'tailwind-merge'

/** Small colored tag for categorization or status labeling. */
const Pill = ({
  children,
  color,
  className,
}: {
  children: React.ReactNode
  color: 'gray' | 'info' | 'teal' | 'amber' | 'red' | 'green'
  className?: string
}) => {
  return (
    <span
      className={twMerge(
        'inline-flex items-center space-x-1 rounded-full px-1.5 py-0.5 text-xs font-medium whitespace-nowrap backdrop-blur-2xl backdrop-saturate-150 transition-all duration-200',

        color === 'info'
          ? 'border border-slate-300/12 bg-slate-500/6 text-slate-600 dark:border-slate-500/8 dark:bg-slate-500/4 dark:text-slate-300'
          : '',
        color === 'gray'
          ? 'border border-white/8 bg-white/4 text-slate-600 dark:border-white/6 dark:bg-white/3 dark:text-slate-300'
          : '',
        color === 'teal'
          ? 'border border-teal-300/12 bg-teal-500/6 text-teal-600 dark:border-teal-500/8 dark:bg-teal-500/4 dark:text-teal-300'
          : '',
        color === 'amber'
          ? 'border border-amber-300/12 bg-amber-500/6 text-amber-600 dark:border-amber-500/8 dark:bg-amber-500/4 dark:text-amber-300'
          : '',
        color === 'red'
          ? 'border border-red-300/12 bg-red-500/6 text-red-600 dark:border-red-500/8 dark:bg-red-500/4 dark:text-red-300'
          : '',
        color === 'green'
          ? 'border border-emerald-300/12 bg-emerald-500/6 text-emerald-600 dark:border-emerald-500/8 dark:bg-emerald-500/4 dark:text-emerald-300'
          : '',
        className,
      )}
    >
      {children}
    </span>
  )
}

export default Pill
