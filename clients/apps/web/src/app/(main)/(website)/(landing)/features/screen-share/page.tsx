import { FeaturePage } from '@/components/Landing/FeaturePage'
import { CONFIG } from '@/utils/config'
import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Screen Share',
  description:
    'End-to-end encrypted P2P screen sharing. No accounts, no servers relaying your pixels — just a direct peer connection between you and your viewers.',
  openGraph: {
    siteName: 'Rapidly',
    type: 'website',
    images: [{ url: CONFIG.OG_IMAGE_URL, width: 1200, height: 630 }],
  },
}

const features = [
  {
    icon: 'Monitor',
    title: 'Direct peer connection',
    description:
      'Your video goes straight from your browser to each viewer over WebRTC. The Rapidly server only helps them find each other.',
  },
  {
    icon: 'Lock',
    title: 'End-to-end encrypted',
    description:
      'DTLS + SRTP by default. Your pixels are never in the clear on a Rapidly machine, and the host secret never leaves the browser.',
  },
  {
    icon: 'Users',
    title: 'Up to 10 viewers',
    description:
      'Each viewer joins with a one-time invite link the host mints on demand. One IP, one connection, bounded by the session cap.',
  },
  {
    icon: 'Wifi',
    title: 'Works behind NATs',
    description:
      'Automatic fallback through Rapidly-hosted TURN when a direct path is not possible, so the share still works on coffee-shop Wi-Fi.',
  },
]

export default function ScreenShareFeaturePage() {
  return (
    <FeaturePage
      description="Share a screen in the browser, without installing anything. End-to-end encrypted, peer-to-peer, and gone the moment everyone closes the tab."
      features={features}
      ctaLabel="Start sharing"
      ctaHref="/screen"
      docsHref={CONFIG.DOCS_BASE_URL}
    />
  )
}
