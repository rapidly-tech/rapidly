import type { Metadata } from 'next'

import { CollabHostClient } from '@/components/Collab/CollabHostClient'
import { ChamberPageShell } from '@/components/Revolver/ChamberPageShell'

export const metadata: Metadata = {
  title: 'Collab — Rapidly',
  description:
    'Realtime collaborative documents, peer-to-peer. No accounts, no servers storing your text, no install.',
}

export default function CollabHostPage() {
  return (
    <ChamberPageShell
      title="Collaborate in real time"
      subtitle="Encrypted peer-to-peer docs and whiteboards, no servers storing your work"
      currentId="collab"
    >
      <CollabHostClient />
    </ChamberPageShell>
  )
}
