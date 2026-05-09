'use client'

import { JSX, useId } from 'react'

export default function ProgressBar({
  value,
  max,
}: {
  value: number
  max: number
}): JSX.Element {
  const id = useId()
  const percentage = max > 0 ? Math.min(100, (value / max) * 100) : 0
  const isComplete = value >= max && max > 0

  return (
    <div
      id={`progress-bar-${id}`}
      className="bg-surface relative h-10 w-full overflow-hidden rounded-xl"
      role="progressbar"
      aria-valuenow={Math.round(percentage)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={`h-full ${
          isComplete
            ? 'bg-linear-to-r from-emerald-500 to-emerald-600'
            : 'bg-linear-to-r from-slate-500 to-slate-600'
        } transition-all duration-300 ease-out`}
        style={{ width: `${percentage}%` }}
      />
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="rp-text-primary text-sm font-semibold drop-shadow-sm">
          {Math.round(percentage)}%
        </span>
      </div>
    </div>
  )
}
