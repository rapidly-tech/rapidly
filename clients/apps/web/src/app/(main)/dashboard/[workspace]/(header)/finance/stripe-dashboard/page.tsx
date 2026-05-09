import { getServerSideAPI } from '@/utils/client/serverside'
import { getWorkspaceBySlugOrNotFound } from '@/utils/workspace'
import { Metadata } from 'next'
import StripeDashboardPage from './StripeDashboardPage'

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: `Finance - Stripe Dashboard`,
  }
}

/** Embedded Stripe dashboard page for managing connected Stripe account details. */
export default async function Page(props: {
  params: Promise<{ workspace: string }>
}) {
  const params = await props.params
  const api = await getServerSideAPI()
  const workspace = await getWorkspaceBySlugOrNotFound(api, params.workspace)

  return <StripeDashboardPage workspace={workspace} />
}
