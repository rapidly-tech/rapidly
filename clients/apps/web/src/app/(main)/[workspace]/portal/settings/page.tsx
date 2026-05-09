import { CustomerPortalSettings } from '@/components/CustomerPortal/CustomerPortalSettings'
import { getServerSideAPI } from '@/utils/client/serverside'
import { orgOgImageUrl } from '@/utils/config'
import { getWorkspaceOrNotFound } from '@/utils/customerPortal'
import type { Metadata } from 'next'

export async function generateMetadata(props: {
  params: Promise<{ workspace: string }>
}): Promise<Metadata> {
  const params = await props.params
  const api = await getServerSideAPI()
  const { workspace } = await getWorkspaceOrNotFound(api, params.workspace)

  return {
    title: `Customer Portal | ${workspace.name}`,
    openGraph: {
      title: `Customer Portal | ${workspace.name} on Rapidly`,
      description: `Customer Portal | ${workspace.name} on Rapidly`,
      siteName: 'Rapidly',
      type: 'website',
      images: [
        {
          url: orgOgImageUrl(workspace.slug),
          width: 1200,
          height: 630,
        },
      ],
    },
    twitter: {
      images: [
        {
          url: orgOgImageUrl(workspace.slug),
          width: 1200,
          height: 630,
          alt: `${workspace.name} on Rapidly`,
        },
      ],
      card: 'summary_large_image',
      title: `Customer Portal | ${workspace.name} on Rapidly`,
      description: `Customer Portal | ${workspace.name} on Rapidly`,
    },
  }
}

/** Customer portal settings page for managing account preferences and session configuration. */
export default async function Page(props: {
  params: Promise<{ workspace: string }>
  searchParams: Promise<{
    customer_session_token?: string
    member_session_token?: string
  }>
}) {
  const { customer_session_token, member_session_token, ...searchParams } =
    await props.searchParams
  const params = await props.params
  const token = customer_session_token ?? member_session_token
  const api = await getServerSideAPI(token)
  const { workspace } = await getWorkspaceOrNotFound(
    api,
    params.workspace,
    searchParams,
  )

  return (
    <CustomerPortalSettings
      workspace={workspace}
      customerSessionToken={token}
    />
  )
}
