import { getServerSideAPI } from '@/utils/client/serverside'
import { getWorkspaceBySlugOrNotFound } from '@/utils/workspace'
import { Metadata } from 'next'
import SendFilesPage from './SendFilesPage'

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: 'Share Files',
  }
}

/** Send files page where workspace members initiate new file shares. */
export default async function Page(props: {
  params: Promise<{ workspace: string }>
}) {
  const params = await props.params
  const api = await getServerSideAPI()
  const workspace = await getWorkspaceBySlugOrNotFound(api, params.workspace)

  return <SendFilesPage workspace={workspace} />
}
