import { getServerSideAPI } from '@/utils/client/serverside'
import { getWorkspaceBySlugOrNotFound } from '@/utils/workspace'
import { Metadata } from 'next'
import WebhooksPage from './WebhooksPage'

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: 'Webhooks',
  }
}

/** Webhooks configuration page for managing webhook endpoints. */
export default async function Page(props: {
  params: Promise<{ workspace: string }>
}) {
  const params = await props.params
  const api = await getServerSideAPI()
  const workspace = await getWorkspaceBySlugOrNotFound(api, params.workspace)

  return <WebhooksPage workspace={workspace} />
}
