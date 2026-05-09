import Login from '@/components/Auth/Login'
import { RapidlyLogotype } from '@/components/Layout/Public/RapidlyLogotype'
import { Icon } from '@iconify/react'
import { Metadata } from 'next'
import Link from 'next/link'

export const metadata: Metadata = {
  title: 'Log in to Rapidly',
}

const LoginHeader = () => (
  <div className="flex flex-col gap-y-8">
    <RapidlyLogotype logoVariant="icon" size={60} href="/" />
    <div className="flex flex-col gap-4">
      <h2 className="rp-text-primary text-2xl">Welcome to Rapidly</h2>
      <h2 className="text-lg text-slate-500 dark:text-slate-400">
        Secure file sharing with encryption and analytics
      </h2>
    </div>
  </div>
)

export default async function Page(props: {
  searchParams: Promise<{ return_to?: string }>
}) {
  const searchParams = await props.searchParams
  const { return_to: returnTo, ...restParams } = searchParams

  return (
    <div className="flex h-screen w-full grow items-center justify-center">
      <div className="relative z-10 flex w-full max-w-md flex-col gap-y-1 rounded-3xl bg-slate-100 p-1 shadow-[0_8px_40px_rgba(0,0,0,0.06)] dark:border dark:border-slate-900 dark:bg-slate-950">
        {/* Title bar */}
        <div className="flex flex-row items-center justify-between pt-1 pr-1 pb-0 pl-4 text-sm">
          <span className="text-slate-500">Login</span>
          <Link
            href="/"
            className="inline-flex size-8 items-center justify-center rounded-full text-slate-500 hover:bg-slate-200 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-400"
            aria-label="Close"
          >
            <Icon icon="solar:close-circle-linear" className="text-[1em]" />
          </Link>
        </div>

        {/* Content area */}
        <div className="flex flex-col justify-between gap-16 rounded-[20px] bg-white p-12 dark:bg-white/5 dark:backdrop-blur-[60px]">
          <LoginHeader />
          <Login returnTo={returnTo} returnParams={restParams} />
        </div>
      </div>
    </div>
  )
}
