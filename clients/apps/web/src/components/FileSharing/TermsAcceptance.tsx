'use client'

import Link from 'next/link'
import { JSX, useCallback, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useModalFocusTrap } from './useModalFocusTrap'

export default function TermsAcceptance(): JSX.Element {
  const [showModal, setShowModal] = useState(false)
  const modalRef = useRef<HTMLDivElement>(null)
  const closeModal = useCallback(() => setShowModal(false), [])
  useModalFocusTrap(showModal, closeModal, modalRef)

  return (
    <>
      <div className="flex justify-center text-center">
        <span className="text-xs text-slate-400 dark:text-slate-500">
          By selecting a file or typing a secret,
          <br />
          you agree to{' '}
          <button
            type="button"
            onClick={() => setShowModal(true)}
            className="underline transition-colors duration-200 hover:text-slate-900 dark:hover:text-slate-200"
            aria-label="View file sharing and secret terms"
          >
            our sharing terms
          </button>
          .
        </span>
      </div>

      {showModal &&
        createPortal(
          <div
            className="fixed inset-0 z-100 flex items-center justify-center bg-black/50 p-4"
            role="dialog"
            aria-modal="true"
            aria-labelledby="terms-modal-title"
            onClick={() => setShowModal(false)}
          >
            <div
              ref={modalRef}
              className="bg-surface-inset w-full max-w-md rounded-xl p-8"
              onClick={(e) => e.stopPropagation()}
            >
              <h2
                id="terms-modal-title"
                className="mb-4 text-xl font-bold text-slate-900 dark:text-slate-50"
              >
                File Sharing &amp; Secret Terms
              </h2>

              <div className="space-y-4 text-slate-600 dark:text-slate-300">
                <p className="text-xs font-semibold tracking-wide text-slate-400 uppercase dark:text-slate-500">
                  File Sharing
                </p>
                <ul className="list-none space-y-3">
                  <li className="bg-surface flex items-start gap-3 rounded-xl px-4 py-3">
                    <span className="shrink-0 text-base">1.</span>
                    <span className="text-sm">
                      Files are shared directly between browsers — no server
                      storage involved
                    </span>
                  </li>
                  <li className="bg-surface flex items-start gap-3 rounded-xl px-4 py-3">
                    <span className="shrink-0 text-base">2.</span>
                    <span className="text-sm">
                      Only upload files you have the right to share
                    </span>
                  </li>
                  <li className="bg-surface flex items-start gap-3 rounded-xl px-4 py-3">
                    <span className="shrink-0 text-base">3.</span>
                    <span className="text-sm">
                      Share download links only with intended recipients
                    </span>
                  </li>
                  <li className="bg-surface flex items-start gap-3 rounded-xl px-4 py-3">
                    <span className="shrink-0 text-base">4.</span>
                    <span className="text-sm">
                      No illegal or harmful content allowed
                    </span>
                  </li>
                </ul>

                <p className="text-xs font-semibold tracking-wide text-slate-400 uppercase dark:text-slate-500">
                  Secrets
                </p>
                <ul className="list-none space-y-3">
                  <li className="bg-surface flex items-start gap-3 rounded-xl px-4 py-3">
                    <span className="shrink-0 text-base">5.</span>
                    <span className="text-sm">
                      Secrets are encrypted on your device and stored
                      temporarily on our servers
                    </span>
                  </li>
                  <li className="bg-surface flex items-start gap-3 rounded-xl px-4 py-3">
                    <span className="shrink-0 text-base">6.</span>
                    <span className="text-sm">
                      Secrets are permanently deleted after a single view or
                      upon expiration
                    </span>
                  </li>
                  <li className="bg-surface flex items-start gap-3 rounded-xl px-4 py-3">
                    <span className="shrink-0 text-base">7.</span>
                    <span className="text-sm">
                      We cannot recover deleted secrets — share links carefully
                    </span>
                  </li>
                </ul>

                <p className="text-sm text-slate-500 dark:text-slate-400">
                  By uploading a file or submitting a secret, you confirm that
                  you understand and agree to these terms. See our full{' '}
                  <Link
                    href="/legal/terms"
                    className="underline hover:text-slate-600 dark:hover:text-slate-300"
                  >
                    Terms of Use
                  </Link>
                  .
                </p>
              </div>

              <div className="mt-6 flex justify-end">
                <button
                  type="button"
                  autoFocus
                  onClick={() => setShowModal(false)}
                  className="rounded-xl bg-slate-600 px-4 py-2 text-sm font-medium text-white transition-colors duration-200 hover:bg-slate-700 dark:bg-slate-500 dark:hover:bg-slate-400"
                >
                  Got it
                </button>
              </div>
            </div>
          </div>,
          document.body,
        )}
    </>
  )
}
