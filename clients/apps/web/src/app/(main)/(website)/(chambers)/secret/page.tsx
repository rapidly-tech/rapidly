import type { Metadata } from 'next'

import { ChamberPageShell } from '@/components/Chamber/ChamberPageShell'
import { SecretSharingForm } from '@/components/Landing/file-sharing/SecretSharingForm'

export const metadata: Metadata = {
  title: 'Secret — Rapidly',
  description:
    'Send an encrypted one-time secret. Self-destructs on open, no account needed.',
}

// Public landing for creating a one-time secret. The sibling route
// ``/secret/[key]`` is the recipient view; this page is the sender
// flow the chamber-strip points at.
export default function SecretCreatePage() {
  return (
    <ChamberPageShell
      title="Send a secret"
      subtitle="Encrypted one-time share — self-destructs on open, no account needed"
      currentId="secret"
    >
      <SecretSharingForm />
    </ChamberPageShell>
  )
}
