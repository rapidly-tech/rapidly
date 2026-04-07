'use client'

import React, { JSX } from 'react'

export default function InputLabel({
  children,
  hasError = false,
  tooltip,
  htmlFor,
}: {
  children: React.ReactNode
  hasError?: boolean
  tooltip?: string
  htmlFor?: string
}): JSX.Element {
  return (
    <div className="relative flex items-center gap-1">
      <label
        htmlFor={htmlFor}
        className={`mb-1 text-xs font-medium ${
          hasError ? 'text-red-500' : 'text-slate-500 dark:text-slate-400'
        }`}
      >
        {children}
      </label>
      {tooltip && (
        <div className="relative">
          <button
            type="button"
            className="peer cursor-help border-none bg-transparent p-0 text-xs text-slate-400 hover:opacity-80 focus:opacity-80 dark:text-slate-500"
            aria-label="More information"
          >
            ⓘ
          </button>
          <div className="pointer-events-none absolute top-full left-0 z-10 mt-1 opacity-0 transition-opacity duration-200 peer-hover:opacity-100 peer-focus:opacity-100 sm:top-1/2 sm:left-full sm:mt-0 sm:ml-1 sm:-translate-y-1/2">
            <div className="w-[min(320px,80vw)] rounded-lg border border-slate-200 bg-slate-100 px-3 py-2 text-xs text-slate-800 shadow-lg dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100">
              {tooltip}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
