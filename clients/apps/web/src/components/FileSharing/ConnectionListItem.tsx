'use client'

import {
  UploaderConnection,
  UploaderConnectionStatus,
} from '@/utils/file-sharing/types'
import { JSX } from 'react'
import ProgressBar from './ProgressBar'

export function ConnectionListItem({
  conn,
}: {
  conn: UploaderConnection
}): JSX.Element {
  // When status is "Ready" but files are still being transferred (completedFiles > 0
  // and < totalFiles), the uploader is just waiting for the next file request —
  // treat it as "uploading" visually to avoid status badge jitter.
  const isTransferInProgress =
    conn.completedFiles > 0 && conn.completedFiles < conn.totalFiles
  const displayStatus =
    conn.status === UploaderConnectionStatus.Ready && isTransferInProgress
      ? UploaderConnectionStatus.Uploading
      : conn.status

  const getStatusColor = (status: UploaderConnectionStatus) => {
    switch (status) {
      case UploaderConnectionStatus.Uploading:
        return 'bg-slate-600'
      case UploaderConnectionStatus.Paused:
        return 'bg-amber-500'
      case UploaderConnectionStatus.Done:
        return 'bg-emerald-500'
      case UploaderConnectionStatus.Closed:
      case UploaderConnectionStatus.InvalidPassword:
      case UploaderConnectionStatus.LockedOut:
        return 'bg-red-500'
      default:
        return 'bg-slate-400 dark:bg-slate-700'
    }
  }

  // Overall progress: bytes sent / total bytes (matches downloader's bytes-based progress)
  const overallPercent =
    conn.totalBytes > 0
      ? Math.round(
          (Math.min(conn.bytesSent, conn.totalBytes) / conn.totalBytes) * 100,
        )
      : 0

  return (
    <div className="bg-surface-inset mt-4 w-full rounded-xl p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex min-w-0 items-center gap-2">
          <span className="truncate text-sm font-medium text-slate-800 dark:text-slate-200">
            {conn.browserName && conn.browserVersion ? (
              <>
                {conn.browserName}{' '}
                <span className="text-slate-400 dark:text-slate-500">
                  v{conn.browserVersion}
                </span>
              </>
            ) : (
              'Downloader'
            )}
          </span>
          <span
            className={`shrink-0 rounded-md px-2 py-0.5 text-[10px] font-medium text-white ${getStatusColor(
              displayStatus,
            )}`}
          >
            {displayStatus.replace(/_/g, ' ').toLowerCase()}
          </span>
        </div>

        <div className="shrink-0 text-right text-xs text-slate-500 dark:text-slate-400">
          <div className="whitespace-nowrap">
            {Math.min(conn.completedFiles, conn.totalFiles)} / {conn.totalFiles}{' '}
            files
          </div>
          {(displayStatus === UploaderConnectionStatus.Uploading ||
            isTransferInProgress) && (
            <div className="whitespace-nowrap text-slate-600 dark:text-slate-400">
              {overallPercent}%
            </div>
          )}
        </div>
      </div>
      <ProgressBar
        value={Math.min(conn.bytesSent, conn.totalBytes)}
        max={conn.totalBytes}
      />
    </div>
  )
}
