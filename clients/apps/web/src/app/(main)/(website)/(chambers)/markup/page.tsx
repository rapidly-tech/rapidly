import type { Metadata } from 'next'

import { ChamberPageShell } from '@/components/Chamber/ChamberPageShell'
import { CollabHostClient } from '@/components/Markup/CollabHostClient'

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
