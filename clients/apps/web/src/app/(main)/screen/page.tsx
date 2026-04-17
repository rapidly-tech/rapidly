import type { Metadata } from 'next'

import { ScreenHostClient } from '@/components/Screen/ScreenHostClient'

export const metadata: Metadata = {
  title: 'Share your screen — Rapidly',
  description:
    'End-to-end encrypted P2P screen sharing with up to 10 viewers. No accounts, no servers relaying your video.',
}

export default function ScreenHostPage() {
  return (
    <div className="flex min-h-[calc(100vh-200px)] items-center justify-center px-4 py-12">
      <ScreenHostClient />
    </div>
  )
}
