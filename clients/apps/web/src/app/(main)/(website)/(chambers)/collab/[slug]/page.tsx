import type { Metadata } from 'next'

import { CollabGuestClient } from '@/components/Collab/CollabGuestClient'

interface PageProps {
  params: Promise<{ slug: string }>
  searchParams: Promise<Record<string, string | string[] | undefined>>
}

export const metadata: Metadata = {
  title: 'Join doc — Rapidly',
  description:
    'Someone is collaborating with you on Rapidly — realtime, peer-to-peer.',
}

export default async function CollabGuestPage({
  params,
  searchParams,
}: PageProps) {
  const { slug } = await params
  const search = await searchParams
  const rawToken = search.t
  const token =
    typeof rawToken === 'string'
      ? rawToken
      : Array.isArray(rawToken)
        ? (rawToken[0] ?? null)
        : null

  return (
    <div className="flex min-h-[calc(100vh-200px)] items-center justify-center px-4 py-12">
      <CollabGuestClient slug={slug} token={token} />
    </div>
  )
}
