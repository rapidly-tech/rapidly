import type { Metadata } from 'next'

import { SecretSharingForm } from '@/components/Landing/file-sharing/SecretSharingForm'

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
    <div className="mx-auto flex min-h-[calc(100vh-200px)] w-full max-w-3xl flex-col items-center justify-center px-4 py-12">
      <SecretSharingForm />
    </div>
  )
}
