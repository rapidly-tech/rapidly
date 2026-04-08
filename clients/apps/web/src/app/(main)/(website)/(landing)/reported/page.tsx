import Button from '@rapidly-tech/ui/components/forms/Button'
import { Metadata } from 'next'
import Link from 'next/link'
import { JSX } from 'react'

export const metadata: Metadata = {
  title: 'Transfer Halted - File Sharing',
  description:
    'This file transfer has been halted due to a terms violation report.',
}

/** Informational page shown when a file transfer has been halted due to a terms violation. */
export default function ReportedPage(): JSX.Element {
  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center gap-y-6 py-16 text-center">
      <h1 className="text-3xl font-semibold tracking-tight md:text-5xl">
        Transfer Halted
      </h1>
      <p className="text-base font-medium tracking-wide text-slate-400 dark:text-slate-500">
        This file transfer has been halted due to a terms violation report
      </p>

      <div className="w-full rounded-xl bg-slate-100 p-4 text-left dark:bg-slate-900">
        <h3 className="mb-4 text-lg font-medium text-slate-800 dark:text-slate-200">
          What happened?
        </h3>
        <p className="mb-4 text-sm leading-relaxed text-slate-600 dark:text-slate-300">
          This file transfer has been halted due to a potential violation of our
          terms of service. Our team reviews reports to ensure the safety and
          integrity of our platform.
        </p>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          If you believe this was a mistake, please contact{' '}
          <a
            href="mailto:support@rapidly.tech"
            className="text-slate-600 hover:underline dark:text-slate-400"
          >
            support@rapidly.tech
          </a>
          .
        </p>
      </div>

      <Button asChild>
        <Link href="/">Return to File Sharing</Link>
      </Button>
    </div>
  )
}
