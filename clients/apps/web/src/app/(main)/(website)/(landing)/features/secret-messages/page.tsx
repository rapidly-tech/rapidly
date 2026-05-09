import { FeaturePage } from '@/components/Landing/FeaturePage'
import { CONFIG } from '@/utils/config'
import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Secret Messages',
  description:
    'Send encrypted secrets and files that self-destruct after one view. OpenPGP encrypted, server-stored, zero knowledge.',
  openGraph: {
    siteName: 'Rapidly',
    type: 'website',
    images: [{ url: CONFIG.OG_IMAGE_URL, width: 1200, height: 630 }],
  },
}

const features = [
  {
    icon: 'Lock',
    title: 'OpenPGP Encryption',
    description:
      'Every secret is encrypted with OpenPGP before it reaches our servers. The decryption key lives only in the share link.',
  },
  {
    icon: 'Cloud',
    title: 'Server-Stored',
    description:
      'Encrypted secrets are stored on our servers so the recipient can access them at any time — no need for both parties to be online.',
  },
  {
    icon: 'Eye',
    title: 'One-Time View',
    description:
      'Each secret can only be viewed once. After the recipient opens it, the encrypted data is permanently deleted.',
  },
  {
    icon: 'Trash2',
    title: 'Auto-Delete',
    description:
      'Unclaimed secrets are automatically purged after expiration. No lingering data, no cleanup needed.',
  },
]

export default function SecretMessagesFeaturePage() {
  return (
    <FeaturePage
      description="Send encrypted secrets and files that self-destruct after one view. No accounts needed, no traces left behind."
      features={features}
      ctaLabel="Send a Secret"
      ctaHref="/"
      docsHref={CONFIG.DOCS_BASE_URL}
    />
  )
}
