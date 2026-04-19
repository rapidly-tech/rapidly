import type { Metadata } from 'next'

import { ChamberPageShell } from '@/components/Revolver/ChamberPageShell'
import { ScreenHostClient } from '@/components/Screen/ScreenHostClient'

export const metadata: Metadata = {
  title: 'Share your screen — Rapidly',
  description:
    'End-to-end encrypted P2P screen sharing with up to 10 viewers. No accounts, no servers relaying your video.',
}

export default function ScreenHostPage() {
  return (
    <ChamberPageShell
      title="Share your screen"
      subtitle="Encrypted peer-to-peer — no uploads, no relays, up to 10 viewers"
      currentId="screen"
    >
      <ScreenHostClient />
    </ChamberPageShell>
  )
}
