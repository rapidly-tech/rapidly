import { WarningIcon } from '@/components/FileSharing/Icons'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Link from 'next/link'
import { JSX } from 'react'

interface DownloadClientProps {
  slug: string
}

/**
 * Legacy download route — no longer functional for encrypted transfers.
 *
 * All file sharing now uses hash-based URLs (/#/d/{slug}/k/{key}/s/{salt})
 * which carry the encryption key in the URL fragment. This server-rendered
 * route cannot access the fragment, so it cannot decrypt files.
 */
export default function DownloadClient({
  slug: _slug,
}: DownloadClientProps): JSX.Element {
  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center gap-y-6 text-center">
      <h1 className="text-3xl font-semibold tracking-tight md:text-5xl">
        Invalid Download Link
      </h1>
      <p className="text-base font-medium tracking-wide text-slate-400 dark:text-slate-500">
        This link format is no longer supported
      </p>

      <div className="flex w-full items-center gap-x-2 rounded-lg bg-amber-50 px-4 py-3 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400">
        <WarningIcon className="h-5 w-5 shrink-0" />
        <span className="text-sm">
          Please ask the sender for a new share link. Share links include an
          encryption key that must be part of the URL to decrypt files securely.
        </span>
      </div>

      <Button asChild>
        <Link href="/">Return to File Sharing</Link>
      </Button>
    </div>
  )
}
