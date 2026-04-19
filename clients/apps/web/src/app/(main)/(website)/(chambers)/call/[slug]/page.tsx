import type { Metadata } from 'next'

import { CallGuestClient } from '@/components/Call/CallGuestClient'

interface PageProps {
  params: Promise<{ slug: string }>
  searchParams: Promise<Record<string, string | string[] | undefined>>
}

export const metadata: Metadata = {
  title: 'Join call — Rapidly',
  description:
    'Someone is calling you on Rapidly — end-to-end encrypted, peer-to-peer.',
}

export default async function CallGuestPage({
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
      <CallGuestClient slug={slug} token={token} />
    </div>
  )
}
