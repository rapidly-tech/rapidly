import type { Metadata } from 'next'

import { CallHostClient } from '@/components/Call/CallHostClient'
import { ChamberPageShell } from '@/components/Revolver/ChamberPageShell'

export const metadata: Metadata = {
  title: 'Call — Rapidly',
  description:
    'End-to-end encrypted peer-to-peer voice & video calls. No accounts, no servers relaying your stream.',
}

export default function CallHostPage() {
  return (
    <ChamberPageShell
      title="Start a call"
      subtitle="Encrypted voice and video, peer-to-peer — no accounts, no relays"
      currentId="call"
    >
      <CallHostClient />
    </ChamberPageShell>
  )
}
