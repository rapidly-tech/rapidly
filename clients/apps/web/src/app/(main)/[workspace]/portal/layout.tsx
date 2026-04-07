import { Toaster } from '@/components/Toast/Toaster'
import { getServerSideAPI } from '@/utils/client/serverside'
import { getWorkspaceOrNotFound } from '@/utils/customerPortal'
import Avatar from '@rapidly-tech/ui/components/data/Avatar'
import { CustomerPortalLayoutWrapper } from './CustomerPortalLayoutWrapper'
import { Navigation } from './Navigation'

export const dynamic = 'force-dynamic'

export default async function Layout(props: {
  params: Promise<{ workspace: string }>
  children: React.ReactNode
}) {
  const params = await props.params

  const { children } = props

  const api = await getServerSideAPI()
  const { workspace } = await getWorkspaceOrNotFound(api, params.workspace)

  return (
    <div className="flex min-h-screen grow flex-col">
      <div className="flex w-full flex-col">
        <div className="flex flex-col justify-center gap-y-12 px-4 py-4 lg:px-8 lg:py-8">
          <Avatar
            className="h-8 w-8"
            avatar_url={workspace.avatar_url}
            name={workspace.name}
          />
        </div>
      </div>
      <CustomerPortalLayoutWrapper workspace={workspace}>
        <div className="flex w-full flex-col items-stretch gap-6 px-4 py-8 md:mx-auto md:max-w-5xl md:flex-row md:gap-12 lg:px-0">
          <Navigation workspace={workspace} />
          <div className="flex w-full flex-col md:py-12">{children}</div>
        </div>
      </CustomerPortalLayoutWrapper>
      <Toaster />
    </div>
  )
}
