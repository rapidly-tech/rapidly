import type { Metadata } from 'next'

import { CallHostClient } from '@/components/Call/CallHostClient'

export const metadata: Metadata = {
  title: 'Call — Rapidly',
  description:
    'End-to-end encrypted peer-to-peer voice & video calls. No accounts, no servers relaying your stream.',
}

export default function CallHostPage() {
  return (
    <div className="flex min-h-[calc(100vh-200px)] items-center justify-center px-4 py-12">
      <CallHostClient />
    </div>
  )
}
