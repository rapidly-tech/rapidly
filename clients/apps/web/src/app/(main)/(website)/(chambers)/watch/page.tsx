import type { Metadata } from 'next'

import { WatchHostClient } from '@/components/Watch/WatchHostClient'

export const metadata: Metadata = {
  title: 'Watch together — Rapidly',
  description:
    'Synced peer-to-peer watch party. Pick a video URL and invite up to 10 viewers — every play, pause, and seek stays in lockstep.',
}

export default function WatchHostPage() {
  return (
    <div className="flex min-h-[calc(100vh-200px)] items-center justify-center px-4 py-12">
      <WatchHostClient />
    </div>
  )
}
