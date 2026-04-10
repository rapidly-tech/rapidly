import { getServerSideAPI } from '@/utils/client/serverside'
import { getWorkspaceBySlugOrNotFound } from '@/utils/workspace'
import { Metadata } from 'next'
import IncomePage from './IncomePage'

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: 'Finance',
  }
}

/** Income overview page summarizing revenue and transaction data for the workspace. */
export default async function Page(props: {
  params: Promise<{ workspace: string }>
}) {
  const params = await props.params
  const api = await getServerSideAPI()
  const workspace = await getWorkspaceBySlugOrNotFound(api, params.workspace)

  return <IncomePage workspace={workspace} />
}
