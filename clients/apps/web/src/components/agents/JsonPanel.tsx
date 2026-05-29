/**
 * Shared JSON panel used across the Agents chamber detail pages
 * (run / eval-run / dataset case rows). Previously copied
 * verbatim into three page files; pulled here so the layout, the
 * dashed-placeholder treatment for ``data === null``, and the
 * new Copy button stay in sync across surfaces.
 *
 * Render shape:
 *   title (uppercase)            [Copy button — when data set]
 *   ┌────────────────────────┐
 *   │ pretty-printed JSON or │
 *   │ dashed placeholder     │
 *   └────────────────────────┘
 */
'use client'

import { useEffect, useState } from 'react'

export function JsonPanel({
  title,
  data,
  placeholder,
  maxHeightClass,
}: {
  title: string
  data: Record<string, unknown> | null
  /** Text shown inside the dashed banner when ``data`` is null.
   *  Defaults to an em-dash so the layout doesn't jump on
   *  optional fields. */
  placeholder?: string
  /** Optional Tailwind ``max-h-*`` class that caps the
   *  rendered ``<pre>`` height and adds a vertical scroll. Use
   *  for surfaces (e.g. the workflow-version graph viewer) where
   *  an unbounded panel would push the rest of the page off-
   *  screen. */
  maxHeightClass?: string
}) {
  const [copied, setCopied] = useState(false)

  // Reset the "Copied!" label after a short beat so the button
  // doesn't stay stuck reading "Copied!" forever.
  useEffect(() => {
    if (!copied) return
    const handle = window.setTimeout(() => setCopied(false), 1500)
    return () => window.clearTimeout(handle)
  }, [copied])

  const onCopy = async () => {
    if (data === null) return
    try {
      await navigator.clipboard.writeText(JSON.stringify(data, null, 2))
      setCopied(true)
    } catch {
      // Clipboard API rejects on insecure origins or when the
      // document is hidden — fall back to a no-op so the click
      // doesn't bubble an exception. Operators can still
      // select + Cmd-C inside the <pre>.
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-xs tracking-wide text-slate-400 uppercase dark:text-slate-500">
          {title}
        </h3>
        {data !== null && (
          <button
            type="button"
            onClick={onCopy}
            className="rounded-md border border-slate-200 px-2 py-0.5 text-[10px] font-medium tracking-wide text-slate-600 uppercase hover:bg-slate-50 dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-800"
            aria-label={`Copy ${title.toLowerCase()} as JSON`}
          >
            {copied ? 'Copied!' : 'Copy'}
          </button>
        )}
      </div>
      {data === null ? (
        <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-500 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-400">
          {placeholder ?? '—'}
        </p>
      ) : (
        <pre
          className={`rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-300 ${
            maxHeightClass
              ? `${maxHeightClass} overflow-auto`
              : 'overflow-x-auto'
          }`}
        >
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  )
}
