import { FeaturePage } from '@/components/Landing/FeaturePage'
import { CONFIG } from '@/utils/config'
import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Secure Sharing',
  description:
    'Encrypted peer-to-peer file transfers, directly in your browser. No uploads, no size limits, no compromises.',
  openGraph: {
    siteName: 'Rapidly',
    type: 'website',
    images: [{ url: CONFIG.OG_IMAGE_URL, width: 1200, height: 630 }],
  },
}

const features = [
  {
    icon: 'Lock',
    title: 'AES-256 Encryption',
    description:
      'Every file is encrypted with AES-256-GCM before leaving your device. Only the recipient can decrypt it.',
  },
  {
    icon: 'ArrowLeftRight',
    title: 'Peer-to-Peer',
    description:
      'Files transfer directly between browsers using WebRTC. No server ever sees your data.',
  },
  {
    icon: 'Infinity',
    title: 'No Size Limits',
    description:
      'Share files of any size — from documents to multi-gigabyte archives — with no upload restrictions.',
  },
  {
    icon: 'ShieldCheck',
    title: 'Zero Knowledge',
    description:
      'We never have access to your files or encryption keys. Your data stays yours.',
  },
]

export default function SharesFeaturePage() {
  return (
    <FeaturePage
      description="Encrypted peer-to-peer file transfers, directly in your browser. No uploads, no size limits, no compromises."
      features={features}
      ctaLabel="Start Sharing"
      ctaHref="/"
      docsHref={CONFIG.DOCS_BASE_URL}
    />
  )
}
