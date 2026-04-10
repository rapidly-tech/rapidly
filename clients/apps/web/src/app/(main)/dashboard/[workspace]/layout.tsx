import { WorkspaceContextProvider } from '@/providers/workspaceContext'
import { getServerSideAPI } from '@/utils/client/serverside'
import { ROUTES } from '@/utils/routes'
import { getWorkspaceMemberships } from '@/utils/user'
import { getWorkspaceBySlug } from '@/utils/workspace'
import { Metadata } from 'next'
import { redirect } from 'next/navigation'
import type { ReactNode } from 'react'

export async function generateMetadata(props: {
  params: Promise<{ workspace: string }>
}): Promise<Metadata> {
  const params = await props.params
  const api = await getServerSideAPI()
  const workspace = await getWorkspaceBySlug(api, params.workspace)
  if (!workspace) {
    return { title: 'Rapidly' }
  }
  return {
    title: {
      template: `%s | ${workspace.name} | Rapidly`,
      default: workspace.name,
    },
  }
}

/** Workspace-scoped dashboard layout that resolves the org and provides context to child routes. */
export default async function Layout(props: {
  params: Promise<{ workspace: string }>
  children: ReactNode
}) {
  const params = await props.params

  const { children } = props

  const api = await getServerSideAPI()
  const workspace = await getWorkspaceBySlug(api, params.workspace)

  if (!workspace) {
    redirect(ROUTES.DASHBOARD.ROOT)
  }

  let userWorkspaces = await getWorkspaceMemberships(api, false)

  // If the workspace is not in the user's workspaces, refetch bypassing the cache
  // This avoids race conditions with new workspaces (e.g. during onboarding) without losing
  // the cache in 99% of the cases
  if (!userWorkspaces.some((org) => org.id === workspace.id)) {
    userWorkspaces = await getWorkspaceMemberships(api, true)
  }

  // If we can't find the workspace even after a refresh, redirect
  if (!userWorkspaces.some((org) => org.id === workspace.id)) {
    return redirect(ROUTES.DASHBOARD.ROOT)
  }

  return (
    <WorkspaceContextProvider workspace={workspace} workspaces={userWorkspaces}>
      {children}
    </WorkspaceContextProvider>
  )
}
