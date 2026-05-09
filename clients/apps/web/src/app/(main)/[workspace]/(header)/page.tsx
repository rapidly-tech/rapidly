import { getServerSideAPI } from '@/utils/client/serverside'
import { orgOgImageUrl } from '@/utils/config'
import { getStorefrontOrNotFound } from '@/utils/storefront'
import type { Metadata } from 'next'
import AppPage from './AppPage'

export async function generateMetadata(props: {
  params: Promise<{ workspace: string }>
}): Promise<Metadata> {
  const params = await props.params
  const api = await getServerSideAPI()
  const { workspace } = await getStorefrontOrNotFound(api, params.workspace)

  return {
    title: `${workspace.name}`,
    description: `${workspace.name} on Rapidly`,
    openGraph: {
      title: `${workspace.name} on Rapidly`,
      description: `${workspace.name} on Rapidly`,
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
      title: `${workspace.name} on Rapidly`,
      description: `${workspace.name} on Rapidly`,
    },
  }
}

/** Public storefront page displaying an workspace's profile and available file shares. */
export default async function Page(props: {
  params: Promise<{ workspace: string }>
}) {
  const params = await props.params
  const api = await getServerSideAPI()
  const storefront = await getStorefrontOrNotFound(api, params.workspace)

  return (
    <AppPage
      workspace={storefront.workspace}
      fileShares={storefront.file_shares}
      secrets={storefront.secrets ?? []}
    />
  )
}
