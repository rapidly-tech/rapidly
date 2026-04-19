import type { Metadata } from 'next'

import { SecretSharingForm } from '@/components/Landing/file-sharing/SecretSharingForm'
import { ChamberPageShell } from '@/components/Revolver/ChamberPageShell'

export const metadata: Metadata = {
  title: 'Secret — Rapidly',
  description:
    'Send an encrypted one-time secret. Self-destructs on open, no account needed.',
}

// Revolver's Secret chamber points here. Without this page clicking
// Secret in the 6-chamber radial used to 404 — the existing sibling
// route /secret/[key] is only the recipient view.
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
