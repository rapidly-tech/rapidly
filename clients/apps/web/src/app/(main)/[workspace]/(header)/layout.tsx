import { RapidlyLogotype } from '@/components/Layout/Public/RapidlyLogotype'
import TopbarRight from '@/components/Layout/Public/TopbarRight'
import PublicLayout from '@/components/Layout/PublicLayout'
import { StorefrontHeader } from '@/components/Profile/StorefrontHeader'
import { StorefrontNav } from '@/components/Workspace/StorefrontNav'
import { getServerSideAPI } from '@/utils/client/serverside'
import { getStorefrontOrNotFound } from '@/utils/storefront'
import { getAuthenticatedUser } from '@/utils/user'
import type { ReactNode } from 'react'

export default async function Layout(props: {
  params: Promise<{ workspace: string }>
  children: ReactNode
}) {
  const params = await props.params

  const { children } = props

  const api = await getServerSideAPI()

  const { workspace } = await getStorefrontOrNotFound(api, params.workspace)

  const authenticatedUser = await getAuthenticatedUser()

  return (
    <PublicLayout className="gap-y-0 py-6 md:py-12" wide>
      <div className="relative flex flex-row items-center justify-end gap-x-6">
        <RapidlyLogotype
          className="absolute left-1/2 -translate-x-1/2"
          size={50}
          href="/"
        />

        <TopbarRight
          authenticatedUser={authenticatedUser}
          storefrontOrg={workspace}
        />
      </div>
      <div className="flex flex-col gap-y-8">
        <div className="flex grow flex-col items-center">
          <StorefrontHeader workspace={workspace} />
        </div>
        <div className="flex flex-col items-center">
          <StorefrontNav workspace={workspace} />
        </div>
        <div className="flex h-full grow flex-col gap-y-8 md:gap-y-16 md:py-12">
          {children}
        </div>
      </div>
    </PublicLayout>
  )
}
