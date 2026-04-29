'use client'

import MicrosoftLoginButton from '@/components/Auth/MicrosoftLoginButton'
import { useAuth } from '@/hooks'
import { Icon } from '@iconify/react'
import { schemas } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { RapidlyLogotype } from './RapidlyLogotype'
import TopbarRight from './TopbarRight'

const Topbar = ({
  hideProfile,
  authenticatedUser,
  userWorkspaces,
}: {
  hideProfile?: boolean
  authenticatedUser: schemas['UserRead'] | undefined
  userWorkspaces: schemas['Workspace'][]
}) => {
  // Fallback to client side user loading
  const { currentUser: clientCurrentUser } = useAuth()
  const currentUser = authenticatedUser ?? clientCurrentUser

  const hasOrgs = Boolean(userWorkspaces && userWorkspaces.length > 0)

  const creatorPath = `/dashboard/${userWorkspaces?.[0]?.slug}`

  const microsoftAccount = currentUser?.oauth_accounts.find(
    (o) => o.platform === 'microsoft',
  )
  const shouldShowMicrosoftAuthUpsell = !microsoftAccount

  const pathname = usePathname()
  const returnTo = pathname ?? '/start'

  const upsellOrDashboard = () => {
    if (!currentUser) {
      return null
    }

    return (
      <>
        {shouldShowMicrosoftAuthUpsell && (
          <MicrosoftLoginButton
            text="Connect with Microsoft"
            returnTo={returnTo}
          />
        )}
        {!hasOrgs && (
          <Link href="/dashboard">
            <Button
              type="button"
              className="space-x-2 border border-white/[0.15] bg-violet-600/85 p-2 px-4 text-sm text-white shadow-md backdrop-blur-2xl backdrop-saturate-150 hover:bg-violet-600/95 hover:shadow-lg hover:shadow-violet-500/25 dark:bg-violet-500/80 dark:hover:bg-violet-500/90"
            >
              <div className="flex flex-row items-center gap-x-2">
                <span className="whitespace-nowrap">Paid Share</span>
                <Icon icon="solar:arrow-right-linear" className="text-[1em]" />
              </div>
            </Button>
          </Link>
        )}
        {hasOrgs && (
          <Link href={creatorPath}>
            <Button className="border border-white/[0.15] bg-violet-600/85 text-white shadow-md backdrop-blur-2xl backdrop-saturate-150 hover:bg-violet-600/95 hover:shadow-lg hover:shadow-violet-500/25 dark:bg-violet-500/80 dark:hover:bg-violet-500/90">
              <div className="flex flex-row items-center gap-x-2">
                <span className="text-xs whitespace-nowrap">Paid Share</span>
              </div>
            </Button>
          </Link>
        )}
      </>
    )
  }

  const upsell = upsellOrDashboard()

  return (
    <div className="z-50 flex w-full flex-col items-center py-4">
      <div className="flex w-full max-w-7xl flex-row flex-wrap justify-between gap-y-4 px-2">
        <div className="flex shrink-0 flex-row items-center gap-x-4 md:gap-x-12">
          <RapidlyLogotype href="/" />
        </div>
        {!hideProfile ? (
          <div className="relative flex flex-1 shrink-0 flex-row items-center justify-end gap-x-6 md:ml-0">
            {upsell}
            <TopbarRight authenticatedUser={authenticatedUser} />
          </div>
        ) : null}
      </div>
    </div>
  )
}

export default Topbar
