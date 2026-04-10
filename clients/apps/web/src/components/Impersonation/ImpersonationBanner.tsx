import { headers } from 'next/headers'

const BACKOFFICE_URL = process.env.NEXT_PUBLIC_BACKOFFICE_URL

/** Server component that renders an impersonation banner when the httpOnly indicator cookie is present. */
export default async function ImpersonationBanner() {
  const headersList = await headers()
  const isImpersonating = headersList.get('x-rapidly-impersonating') === '1'

  if (!isImpersonating) return null

  const exitURL = `${BACKOFFICE_URL}/impersonation/end`

  return (
    <div className="sticky top-0 z-50 flex flex-row items-center justify-between bg-red-100 px-8 py-2 text-sm text-red-600 dark:bg-red-950 dark:text-red-400">
      <div className="flex-[1_0_0]" />
      <div className="hidden flex-[1_0_0] font-medium md:block">
        You are currently impersonating another user
      </div>
      <div className="flex-[1_0_0] text-right">
        <form method="POST" action={exitURL} className="inline">
          <button type="submit" className="font-bold hover:opacity-50">
            Exit impersonation
          </button>
        </form>
      </div>
    </div>
  )
}
