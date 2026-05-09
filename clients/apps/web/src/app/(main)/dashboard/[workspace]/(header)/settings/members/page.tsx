import { getServerSideAPI } from '@/utils/client/serverside'
import { getWorkspaceBySlugOrNotFound } from '@/utils/workspace'
import { Metadata } from 'next'
import MembersPage from './MembersPage'

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: 'Members',
  }
}

/** Members management page for inviting and managing workspace team members. */
export default async function Page(props: {
  params: Promise<{ workspace: string }>
}) {
  const params = await props.params
  const api = await getServerSideAPI()
  const workspace = await getWorkspaceBySlugOrNotFound(api, params.workspace)

  return <MembersPage workspace={workspace} />
}
