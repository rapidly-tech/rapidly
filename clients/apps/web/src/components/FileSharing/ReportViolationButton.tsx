'use client'

import { useReportViolation } from '@/hooks/file-sharing'
import { REPORTED_PAGE } from '@/utils/file-sharing/constants'
import { logger } from '@/utils/file-sharing/logger'
import { JSX, useCallback, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useModalFocusTrap } from './useModalFocusTrap'

export default function ReportViolationButton({
  slug,
  readerToken,
}: {
  slug: string
  readerToken?: string
}): JSX.Element {
  const [showModal, setShowModal] = useState(false)
  const [reportError, setReportError] = useState<string | null>(null)
  const modalContentRef = useRef<HTMLDivElement>(null)
  const closeModal = useCallback(() => setShowModal(false), [])
  useModalFocusTrap(showModal, closeModal, modalContentRef)

  const reportMutation = useReportViolation()

  const handleReport = useCallback(async () => {
    try {
      await reportMutation.mutateAsync({ slug, readerToken })
      window.location.href = REPORTED_PAGE
    } catch (error) {
      logger.error('Failed to report violation', error)
      setReportError(
        error instanceof Error
          ? error.message
          : 'Network error — could not submit report. Please check your connection and try again.',
      )
    }
  }, [slug, readerToken, reportMutation])

  return (
    <>
      <div className="flex justify-center">
        <button
          type="button"
          onClick={() => {
            setReportError(null)
            setShowModal(true)
          }}
          className="text-sm text-red-500 transition-colors duration-200 hover:underline dark:text-red-400"
          aria-label="Report terms violation"
        >
          Report suspicious content
        </button>
      </div>

      {showModal &&
        createPortal(
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
            role="dialog"
            aria-modal="true"
            aria-labelledby="report-modal-title"
            onClick={() => setShowModal(false)}
          >
            <div
              ref={modalContentRef}
              className="bg-surface-inset w-full max-w-md rounded-xl p-8"
              onClick={(e) => e.stopPropagation()}
            >
              <h2
                id="report-modal-title"
                className="mb-4 text-xl font-bold text-slate-900 dark:text-slate-50"
              >
                Report suspicious content?
              </h2>

              <div className="space-y-4 text-slate-600 dark:text-slate-300">
                <p>
                  Before reporting, please confirm this content violates our
                  terms:
                </p>

                <ul className="list-none space-y-3">
                  <li className="bg-surface flex items-start gap-3 rounded-xl px-4 py-3">
                    <span className="text-sm">
                      The content appears to be illegal or harmful
                    </span>
                  </li>
                  <li className="bg-surface flex items-start gap-3 rounded-xl px-4 py-3">
                    <span className="text-sm">
                      The content infringes on copyright or other rights
                    </span>
                  </li>
                  <li className="bg-surface flex items-start gap-3 rounded-xl px-4 py-3">
                    <span className="text-sm">
                      The content was shared without proper authorization
                    </span>
                  </li>
                </ul>

                <p className="text-sm text-slate-500 dark:text-slate-400">
                  Reporting will disconnect new downloaders from this share.
                  Active transfers in progress may continue until complete.
                </p>
              </div>

              {reportError && (
                <p className="mt-4 text-sm text-red-500 dark:text-red-400">
                  {reportError}
                </p>
              )}

              <div className="mt-6 flex justify-end gap-3">
                <button
                  type="button"
                  autoFocus
                  onClick={() => setShowModal(false)}
                  className="bg-surface-inset rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition-colors duration-200 hover:bg-slate-50 dark:border-slate-800 dark:text-slate-200 dark:hover:bg-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={reportMutation.isPending}
                  onClick={handleReport}
                  className="rounded-xl bg-red-500 px-4 py-2 text-sm font-medium text-white transition-colors duration-200 hover:bg-red-600 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-red-600 dark:hover:bg-red-500"
                  aria-label="Confirm report"
                >
                  {reportMutation.isPending ? 'Reporting...' : 'Report'}
                </button>
              </div>
            </div>
          </div>,
          document.body,
        )}
    </>
  )
}
