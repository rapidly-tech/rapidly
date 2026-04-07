import { getServerSideAPI } from '@/utils/client/serverside'
import { getWorkspaceBySlugOrNotFound } from '@/utils/workspace'
import { Metadata } from 'next'
import AccountPage from './AccountPage'

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: `Finance - Payout Account`,
  }
}

/** Payout account page for viewing and managing the workspace's payout settings. */
export default async function Page(props: {
  params: Promise<{ workspace: string }>
}) {
  const params = await props.params
  const api = await getServerSideAPI()
  const workspace = await getWorkspaceBySlugOrNotFound(api, params.workspace)

  return <AccountPage workspace={workspace} />
}
