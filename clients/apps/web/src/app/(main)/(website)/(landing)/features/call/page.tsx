import { FeaturePage } from '@/components/Landing/FeaturePage'
import { CONFIG } from '@/utils/config'
import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Call',
  description:
    'End-to-end encrypted peer-to-peer voice & video calls. No accounts, no servers relaying your stream, no install.',
  openGraph: {
    siteName: 'Rapidly',
    type: 'website',
    images: [{ url: CONFIG.OG_IMAGE_URL, width: 1200, height: 630 }],
  },
}

const features = [
  {
    icon: 'Phone',
    title: 'Pure P2P',
    description:
      'Your audio and video go direct from your browser to the other participant. The Rapidly server only helps you find each other.',
  },
  {
    icon: 'Lock',
    title: 'End-to-end encrypted',
    description:
      'DTLS + SRTP on every connection. No Rapidly machine ever sees your stream in the clear, and no host key leaves the browser.',
  },
  {
    icon: 'Mic',
    title: 'Audio-only or A/V',
    description:
      'Pick audio-only for quick check-ins or bring the camera along. Mute and camera toggles on both sides, of course.',
  },
  {
    icon: 'Wifi',
    title: 'Works behind NATs',
    description:
      'Automatic Rapidly-hosted TURN fallback when a direct path is not possible, so your call still connects on coffee-shop Wi-Fi.',
  },
]

export default function CallFeaturePage() {
  return (
    <FeaturePage
      description="Call anyone without installing anything. End-to-end encrypted, peer-to-peer, and gone the moment both tabs close."
      features={features}
      ctaLabel="Start a call"
      ctaHref="/call"
      docsHref={CONFIG.DOCS_BASE_URL}
    />
  )
}
