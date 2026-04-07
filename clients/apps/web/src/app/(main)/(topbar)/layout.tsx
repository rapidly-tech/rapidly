import Topbar from '@/components/Layout/Public/Topbar'
import PublicLayout from '@/components/Layout/PublicLayout'
import { getServerSideAPI } from '@/utils/client/serverside'
import { getAuthenticatedUser, getWorkspaceMemberships } from '@/utils/user'

/** Topbar layout rendering a public navigation bar and content area. */
export default async function Layout({
  children,
}: {
  children: React.ReactNode
}) {
  const api = await getServerSideAPI()
  const authenticatedUser = await getAuthenticatedUser()
  const userWorkspaces = await getWorkspaceMemberships(api)

  return (
    <div className="flex flex-col md:gap-y-8">
      <Topbar
        authenticatedUser={authenticatedUser}
        userWorkspaces={userWorkspaces}
      />
      <PublicLayout wide>
        <div className="relative flex min-h-screen w-full flex-col py-4 md:py-0">
          {children}
        </div>
      </PublicLayout>
    </div>
  )
}
