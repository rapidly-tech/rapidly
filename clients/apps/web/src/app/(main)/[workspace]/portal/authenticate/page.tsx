import { getServerSideAPI } from '@/utils/client/serverside'
import { orgOgImageUrl } from '@/utils/config'
import { getWorkspaceOrNotFound } from '@/utils/customerPortal'
import type { Metadata } from 'next'
import AuthenticatePage from './AuthenticatePage'

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

/** Customer portal authentication page for verifying customer session tokens. */
export default async function Page(props: {
  params: Promise<{ workspace: string }>
  searchParams: Promise<{ customer_session_token?: string }>
}) {
  const { customer_session_token, ...searchParams } = await props.searchParams
  const params = await props.params
  const api = await getServerSideAPI(customer_session_token)
  const { workspace } = await getWorkspaceOrNotFound(
    api,
    params.workspace,
    searchParams,
  )

  return <AuthenticatePage workspace={workspace} />
}
