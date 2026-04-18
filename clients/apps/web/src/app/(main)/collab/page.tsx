import type { Metadata } from 'next'

import { CollabHostClient } from '@/components/Collab/CollabHostClient'

export const metadata: Metadata = {
  title: 'Collab — Rapidly',
  description:
    'Realtime collaborative documents, peer-to-peer. No accounts, no servers storing your text, no install.',
}

export default function CollabHostPage() {
  return (
    <div className="flex min-h-[calc(100vh-200px)] items-center justify-center px-4 py-12">
      <CollabHostClient />
    </div>
  )
}
