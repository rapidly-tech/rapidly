import { isValidSlugFormat } from '@/utils/file-sharing/url-parser'
import { Metadata } from 'next'
import { notFound } from 'next/navigation'
import DownloadClient from './DownloadClient'

interface PageProps {
  params: Promise<{
    slug: string[]
  }>
}

export async function generateMetadata({
  params: _params,
}: PageProps): Promise<Metadata> {
  return {
    title: 'Download File — Rapidly',
    description:
      'Someone is sharing a file with you via Rapidly secure P2P transfer.',
  }
}

/** File download page for secure P2P file transfers shared via Rapidly. */
export default async function DownloadPage({ params }: PageProps) {
  const { slug } = await params
  const slugPath = slug.join('/')

  if (!isValidSlugFormat(slugPath)) {
    notFound()
  }

  return (
    <div className="flex min-h-[calc(100vh-200px)] items-center justify-center px-4 py-12">
      <DownloadClient slug={slugPath} />
    </div>
  )
}
