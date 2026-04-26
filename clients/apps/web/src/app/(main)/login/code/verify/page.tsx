import LogoIcon from '@/components/Brand/LogoIcon'
import { Icon } from '@iconify/react'
import { Metadata } from 'next'
import Link from 'next/link'
import VerifyPage from './VerifyPage'

export const metadata: Metadata = {
  title: 'Enter verification code',
}

/** Verification code entry page for email-based login authentication. */
export default async function Page(props: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}) {
  const searchParams = await props.searchParams
  const email = searchParams.email as string
  const return_to = searchParams.return_to as string | undefined
  const error = searchParams.error as string | undefined

  return (
    <div className="rp-page-bg flex h-screen w-full grow items-center justify-center">
      <div className="relative z-10 flex w-full max-w-md flex-col gap-y-1 rounded-3xl bg-slate-100 p-1 shadow-[0_8px_40px_rgba(0,0,0,0.06)] dark:border dark:border-slate-900 dark:bg-slate-950">
        {/* Title bar */}
        <div className="flex flex-row items-center justify-between pt-1 pr-1 pb-0 pl-4 text-sm">
          <span className="text-slate-500">Verification</span>
          <Link
            href="/login"
            className="inline-flex size-8 items-center justify-center rounded-full text-slate-500 hover:bg-slate-200 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-400"
            aria-label="Close"
          >
            <Icon icon="solar:close-circle-linear" className="text-[1em]" />
          </Link>
        </div>

        {/* Content area */}
        <div className="flex flex-col items-center rounded-[20px] bg-white p-12 dark:bg-white/5 dark:backdrop-blur-[60px]">
          <Link href="/">
            <LogoIcon size={60} className="rp-text-primary mb-6" />
          </Link>
          <div className="mb-2 text-center text-slate-500 dark:text-slate-400">
            We sent a verification code to{' '}
            <span className="font-medium text-slate-600 dark:text-slate-500">
              {email}
            </span>
          </div>
          <div className="mb-6 text-center text-sm text-slate-500 dark:text-slate-400">
            Please enter the 6-character code below
          </div>
          <VerifyPage return_to={return_to} error={error} email={email} />
        </div>
      </div>
    </div>
  )
}
