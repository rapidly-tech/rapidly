import { getServerSideAPI } from '@/utils/client/serverside'
import { getWorkspaceBySlugOrNotFound } from '@/utils/workspace'
import { Metadata } from 'next'
import DashboardPage from './DashboardPage'

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: 'Overview',
  }
}

/** Workspace dashboard home page showing an overview of key metrics. */
export default async function Page(props: {
  params: Promise<{ workspace: string }>
}) {
  const params = await props.params
  const api = await getServerSideAPI()
  const workspace = await getWorkspaceBySlugOrNotFound(api, params.workspace)

  return <DashboardPage workspace={workspace} />
}
