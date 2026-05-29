/**
 * Shared Copy-as-curl button used by the run + eval-run detail
 * pages. Each page builds the command string (the endpoints +
 * payloads differ); this component handles the clipboard write,
 * the 1.5s "Copied!" flash, and the silent fall-through when
 * navigator.clipboard rejects (insecure origin / hidden doc).
 *
 * Lives next to the M5.51 CopyId widget and the M5.58 JsonPanel
 * Copy button, which share the same flash-state shape.
 */
'use client'

import { useEffect, useState } from 'react'

export function CopyAsCurlButton({
  command,
  title,
}: {
  /** The full curl invocation that gets copied to the clipboard.
   *  Callers are responsible for shell-escaping any embedded
   *  quotes (use ``replace(/'/g, "'\\''")`` for bash single-quote
   *  contexts). */
  command: string
  /** Tooltip text — usually explains the placeholder
   *  session-cookie value and the scope of the re-trigger. */
  title: string
}) {
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!copied) return
    const handle = window.setTimeout(() => setCopied(false), 1500)
    return () => window.clearTimeout(handle)
  }, [copied])

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(command)
      setCopied(true)
    } catch {
      // Insecure origin / hidden document. Silent — operators
      // can manually assemble the curl from the IDs visible on
      // the page.
    }
  }

  return (
    <button
      type="button"
      onClick={onCopy}
      title={title}
      className="self-start rounded-md border border-slate-200 px-2 py-0.5 text-[10px] font-medium tracking-wide text-slate-600 uppercase hover:bg-slate-50 dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-800"
    >
      {copied ? 'Copied!' : 'Copy as curl'}
    </button>
  )
}

/** Shell-escape a single-quoted bash literal. Use when
 *  inlining JSON / arbitrary text inside ``-d '...'``. */
export function bashSingleQuoteEscape(value: string): string {
  return value.replace(/'/g, `'\\''`)
}
