import type { Metadata } from 'next'

import { WatchGuestClient } from '@/components/Watch/WatchGuestClient'

interface PageProps {
  params: Promise<{ slug: string }>
  searchParams: Promise<Record<string, string | string[] | undefined>>
}

export const metadata: Metadata = {
  title: 'Join watch party — Rapidly',
  description:
    'Someone is hosting a synced video watch party on Rapidly. End-to-end encrypted, peer-to-peer.',
}

export default async function WatchGuestPage({
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
      <WatchGuestClient slug={slug} token={token} />
    </div>
  )
}
