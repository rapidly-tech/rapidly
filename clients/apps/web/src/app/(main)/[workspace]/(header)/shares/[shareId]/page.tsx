import { getServerSideAPI } from '@/utils/client/serverside'
import { orgOgImageUrl } from '@/utils/config'
import { getStorefrontOrNotFound } from '@/utils/storefront'
import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import FileSharePage from './FileSharePage'

export async function generateMetadata(props: {
  params: Promise<{ workspace: string; shareId: string }>
}): Promise<Metadata> {
  const params = await props.params
  const api = await getServerSideAPI()
  const { workspace, file_shares } = await getStorefrontOrNotFound(
    api,
    params.workspace,
  )
  const fileShare = file_shares.find((f) => f.short_slug === params.shareId)

  if (!fileShare) {
    notFound()
  }

  const title = fileShare.title || fileShare.file_name || 'Shared File'

  return {
    title: `${title} by ${workspace.name}`,
    openGraph: {
      title,
      description: `A file shared by ${workspace.name}`,
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
          alt: title,
        },
      ],
      card: 'summary_large_image',
      title,
      description: `A file shared by ${workspace.name}`,
    },
  }
}

/** Detail page for a single file share within an workspace's storefront. */
export default async function Page(props: {
  params: Promise<{ workspace: string; shareId: string }>
}) {
  const params = await props.params
  const api = await getServerSideAPI()
  const { workspace, file_shares } = await getStorefrontOrNotFound(
    api,
    params.workspace,
  )
  const fileShare = file_shares.find((f) => f.short_slug === params.shareId)

  if (!fileShare) {
    notFound()
  }

  return <FileSharePage workspace={workspace} fileShare={fileShare} />
}
