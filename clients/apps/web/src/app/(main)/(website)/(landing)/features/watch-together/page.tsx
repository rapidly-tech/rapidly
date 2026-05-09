import { FeaturePage } from '@/components/Landing/FeaturePage'
import { CONFIG } from '@/utils/config'
import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Watch Together',
  description:
    'Synced peer-to-peer watch party. One host, up to 10 viewers, every play / pause / seek in lockstep. End-to-end encrypted, no accounts.',
  openGraph: {
    siteName: 'Rapidly',
    type: 'website',
    images: [{ url: CONFIG.OG_IMAGE_URL, width: 1200, height: 630 }],
  },
}

const features = [
  {
    icon: 'Play',
    title: 'Host-authoritative clock',
    description:
      'The host is the source of truth for playback state. Guests follow — no split-brain, no "who pressed pause first?".',
  },
  {
    icon: 'Clock',
    title: 'Sub-100 ms sync',
    description:
      'Three-band drift correction: tiny drifts get a silent rate nudge, large drifts get a visible seek. Aim is viewer-imperceptible.',
  },
  {
    icon: 'Lock',
    title: 'End-to-end encrypted',
    description:
      'Sync messages ride the same DataChannel file-sharing uses. DTLS + SCTP at the transport layer — no bytes in the clear on a Rapidly server.',
  },
  {
    icon: 'Users',
    title: 'Up to 10 viewers',
    description:
      'Each viewer joins via a one-time invite token the host mints on demand. One IP per connection, bounded by the session cap.',
  },
]

export default function WatchTogetherFeaturePage() {
  return (
    <FeaturePage
      description="Watch anything together without installing a thing. Paste a video URL, mint an invite link, and your viewers stay in lockstep with you."
      features={features}
      ctaLabel="Start a watch party"
      ctaHref="/watch"
      docsHref={CONFIG.DOCS_BASE_URL}
    />
  )
}
