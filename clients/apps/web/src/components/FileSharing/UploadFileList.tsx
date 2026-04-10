'use client'

import { formatFileSize } from '@/utils/file-sharing/constants'
import { JSX, memo } from 'react'
import TypeBadge from './TypeBadge'

export { formatFileSize }

type UploadedFileLike = {
  fileName: string
  size?: number
  type: string
}

export default memo(function UploadFileList({
  files,
  onRemove,
}: {
  files: UploadedFileLike[]
  onRemove?: (index: number) => void
}): JSX.Element {
  const items = files.map((f: UploadedFileLike, i: number) => (
    <div
      key={`${f.fileName}-${f.size ?? 0}-${i}`}
      className="w-full border-b border-slate-100 last:border-0 dark:border-slate-800"
    >
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex min-w-0 flex-1 flex-col">
          <p className="truncate text-sm font-medium text-slate-800 dark:text-slate-200">
            {f.fileName}
          </p>
          {f.size !== undefined && (
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {formatFileSize(f.size)}
            </p>
          )}
        </div>
        <div className="ml-2 flex items-center gap-2">
          <TypeBadge type={f.type} />
          {onRemove && (
            <button
              type="button"
              onClick={() => onRemove?.(i)}
              className="px-1 text-slate-400 hover:text-slate-600 focus:outline-none dark:text-slate-500 dark:hover:text-slate-300"
              aria-label={`Remove ${f.fileName}`}
            >
              ✕
            </button>
          )}
        </div>
      </div>
    </div>
  ))

  return (
    <div className="bg-surface-inset w-full overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800">
      {items}
    </div>
  )
})
