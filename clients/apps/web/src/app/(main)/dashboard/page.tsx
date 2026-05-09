import { getServerSideAPI } from '@/utils/client/serverside'
import { getLastVisitedOrg } from '@/utils/cookies'
import { ROUTES } from '@/utils/routes'
import { getWorkspaceMemberships } from '@/utils/user'
import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'

/** Dashboard index page that redirects to the last visited or first workspace. */
export default async function Page() {
  const api = await getServerSideAPI()
  const userWorkspaces = await getWorkspaceMemberships(api, true)

  if (userWorkspaces.length === 0) {
    redirect('/start/onboarding')
  }

  const lastVisitedOrg = getLastVisitedOrg(await cookies(), userWorkspaces)
  const workspace = lastVisitedOrg ? lastVisitedOrg : userWorkspaces[0]
  redirect(ROUTES.DASHBOARD.org(workspace.slug))
}
