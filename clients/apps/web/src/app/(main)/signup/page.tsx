import Login from '@/components/Auth/Login'
import LogoIcon from '@/components/Brand/LogoIcon'
import { getServerSideAPI } from '@/utils/client/serverside'
import { getLastVisitedOrg } from '@/utils/cookies'
import { getWorkspaceMemberships } from '@/utils/user'
import { Icon } from '@iconify/react'
import { cookies } from 'next/headers'
import Link from 'next/link'
import { redirect } from 'next/navigation'

/** Sign-up page for new creators, redirecting existing users to their dashboard. */
export default async function Page(props: {
  searchParams: Promise<{
    return_to?: string
  }>
}) {
  const searchParams = await props.searchParams

  const { return_to, ...rest } = searchParams

  const api = await getServerSideAPI()
  const userWorkspaces = await getWorkspaceMemberships(api)

  if (userWorkspaces.length > 0) {
    const lastVisitedOrg = getLastVisitedOrg(await cookies(), userWorkspaces)
    const workspace = lastVisitedOrg ? lastVisitedOrg : userWorkspaces[0]
    redirect(`/dashboard/${workspace.slug}`)
  }

  return (
    <div className="flex h-screen w-full flex-col items-center justify-center">
      <div className="relative z-10 flex w-full max-w-7xl flex-col gap-y-1 rounded-3xl bg-slate-100 p-1 shadow-[0_8px_40px_rgba(0,0,0,0.06)] dark:border dark:border-slate-900 dark:bg-slate-950">
        {/* Title bar */}
        <div className="flex flex-row items-center justify-between pt-1 pr-1 pb-0 pl-4 text-sm">
          <span className="text-slate-500">Sign Up</span>
          <Link
            href="/"
            className="inline-flex size-8 items-center justify-center rounded-full text-slate-500 hover:bg-slate-200 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-400"
            aria-label="Close"
          >
            <Icon icon="solar:close-circle-linear" className="text-[1em]" />
          </Link>
        </div>

        {/* Content area */}
        <div className="grid grid-cols-1 gap-y-12 rounded-[20px] bg-white p-12 md:grid-cols-3 md:gap-x-32 md:py-12 md:pr-0 md:pl-12 dark:bg-white/5 dark:backdrop-blur-[60px]">
          <div className="flex flex-col justify-between gap-y-24">
            <Link href="/">
              <LogoIcon className="rp-text-primary" size={80} />
            </Link>

            <div className="flex flex-col gap-y-4">
              <h1 className="text-3xl">Sign Up</h1>
              <p className="text-xl text-slate-500 dark:text-slate-400">
                Join thousands of developers getting paid to code on their
                passions
              </p>
            </div>

            <div className="flex flex-col gap-y-12">
              <Login
                returnTo={return_to}
                returnParams={rest}
                signup={{
                  intent: 'creator',
                }}
              />
            </div>
          </div>
          <div className="rp-page-bg col-span-2 hidden overflow-hidden rounded-4xl rounded-r-none border border-r-0 border-slate-200 md:flex dark:border-slate-800">
            <picture className="flex h-full">
              <source
                media="(prefers-color-scheme: dark)"
                srcSet={`/assets/landing/transactions_dark.png`}
              />
              {/* eslint-disable-next-line no-restricted-syntax */}
              <img
                className="flex h-full flex-1 object-cover object-left"
                src="/assets/landing/transactions_light.png"
                alt="Dashboard Home"
              />
            </picture>
          </div>
        </div>
      </div>
    </div>
  )
}
