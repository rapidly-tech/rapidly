/**
 * Small Copy-to-clipboard widget for an entity ID.
 *
 * Operators routinely paste full UUIDs into curl / spreadsheets /
 * bug reports. The detail-page headers already render the id in
 * font-mono; this wraps that with a tiny button that flips its
 * label to "Copied!" for a beat after click.
 */
'use client'

import { useEffect, useState } from 'react'

export function CopyId({ id, label = 'id' }: { id: string; label?: string }) {
  const [copied, setCopied] = useState(false)

  // Reset the "Copied!" label after a short beat so the button
  // doesn't stay stuck reading "Copied!" forever.
  useEffect(() => {
    if (!copied) return
    const handle = window.setTimeout(() => setCopied(false), 1500)
    return () => window.clearTimeout(handle)
  }, [copied])

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(id)
      setCopied(true)
    } catch {
      // navigator.clipboard rejects on insecure origins or when
      // the document is hidden. Fall back to a no-op rather than
      // throwing; the operator can still select + Cmd-C the id.
    }
  }

  return (
    <span className="inline-flex items-center gap-2">
      <span className="font-mono text-xs text-slate-500 dark:text-slate-400">
        {id}
      </span>
      <button
        type="button"
        onClick={onCopy}
        className="rounded-md border border-slate-200 px-2 py-0.5 text-[10px] font-medium tracking-wide text-slate-600 uppercase hover:bg-slate-50 dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-800"
        aria-label={`Copy ${label}`}
      >
        {copied ? 'Copied!' : 'Copy'}
      </button>
    </span>
  )
}
