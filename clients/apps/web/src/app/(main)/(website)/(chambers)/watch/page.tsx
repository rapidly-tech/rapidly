import type { Metadata } from 'next'

import { ChamberPageShell } from '@/components/Revolver/ChamberPageShell'
import { WatchHostClient } from '@/components/Watch/WatchHostClient'

export const metadata: Metadata = {
  title: 'Watch together — Rapidly',
  description:
    'Synced peer-to-peer watch party. Pick a video URL and invite up to 10 viewers — every play, pause, and seek stays in lockstep.',
}

export default function WatchHostPage() {
  return (
    <ChamberPageShell
      title="Watch together"
      subtitle="Synced peer-to-peer — every play, pause, and seek stays in lockstep"
      currentId="watch"
    >
      <WatchHostClient />
    </ChamberPageShell>
  )
}
