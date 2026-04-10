import LogoIcon from '@/components/Brand/LogoIcon'
import { CONFIG } from '@/utils/config'
import { Icon } from '@iconify/react'
import Button from '@rapidly-tech/ui/components/forms/Button'
import { Metadata } from 'next'
import Link from 'next/link'

export const metadata: Metadata = {
  title: 'Email Update confirmation',
}

const buildVerifyAction = (returnTo?: string): string => {
  const params = new URLSearchParams({
    ...(returnTo && { return_to: returnTo }),
  })
  return `${CONFIG.BASE_URL}/api/email-update/verify?${params.toString()}`
}

export default async function Page(props: {
  searchParams: Promise<{ token: string; return_to?: string }>
}) {
  const { token, return_to } = await props.searchParams
  const actionUrl = buildVerifyAction(return_to)

  return (
    <div className="rp-page-bg flex h-screen w-full grow items-center justify-center">
      <div className="relative z-10 flex w-full max-w-md flex-col gap-y-1 rounded-3xl bg-slate-100 p-1 shadow-[0_8px_40px_rgba(0,0,0,0.06)] dark:border dark:border-slate-900 dark:bg-slate-950">
        {/* Title bar */}
        <div className="flex flex-row items-center justify-between pt-1 pr-1 pb-0 pl-4 text-sm">
          <span className="text-slate-500">Email Update</span>
          <Link
            href="/"
            className="inline-flex size-8 items-center justify-center rounded-full text-slate-500 hover:bg-slate-200 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-400"
            aria-label="Close"
          >
            <Icon icon="solar:close-circle-linear" className="text-[1em]" />
          </Link>
        </div>

        {/* Content area */}
        <form
          className="flex flex-col items-center gap-4 rounded-[20px] bg-white p-12 dark:bg-white/5 dark:backdrop-blur-[60px]"
          method="POST"
          action={actionUrl}
        >
          <Link href="/">
            <LogoIcon
              size={60}
              className="mb-6 text-slate-600 dark:text-slate-400"
            />
          </Link>
          <div className="text-center text-slate-500 dark:text-slate-400">
            To complete the email update process, please click the button below:
          </div>
          <input type="hidden" name="token" value={token} />
          <Button fullWidth size="lg" type="submit">
            Update the email
          </Button>
        </form>
      </div>
    </div>
  )
}
