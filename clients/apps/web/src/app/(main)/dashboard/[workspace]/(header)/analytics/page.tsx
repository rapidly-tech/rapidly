import { getServerSideAPI } from '@/utils/client/serverside'
import { getWorkspaceBySlugOrNotFound } from '@/utils/workspace'
import { Metadata } from 'next'
import AnalyticsPage from './AnalyticsPage'

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: 'Analytics',
  }
}

/** Analytics page displaying file sharing and download metrics for an workspace. */
export default async function Page(props: {
  params: Promise<{ workspace: string }>
}) {
  const params = await props.params
  const api = await getServerSideAPI()
  const workspace = await getWorkspaceBySlugOrNotFound(api, params.workspace)

  return <AnalyticsPage workspace={workspace} />
}
