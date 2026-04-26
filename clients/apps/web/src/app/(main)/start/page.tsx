import { getServerSideAPI } from '@/utils/client/serverside'
import { getLastVisitedOrg } from '@/utils/cookies'
import { ROUTES } from '@/utils/routes'
import { getWorkspaceMemberships } from '@/utils/user'
import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'

/**
 * An authenticated user is automatically redirected to this page when accessing `/` instead of seeing the landing page.
 * This is done in [`next.config.mjs`](../../../next.config.mjs).
 *
 * This page aims at determining where to redirect an authenticated user.
 *
 * - If the user has no workspaces, redirect them to the onboarding page to create one.
 * - If the user has workspaces and a last visited workspace, redirect them to that workspace's dashboard.
 * - Otherwise, redirect them to the first workspace's dashboard.
 */

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
