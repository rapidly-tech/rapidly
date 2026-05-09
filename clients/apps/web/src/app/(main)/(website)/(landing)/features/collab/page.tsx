import { FeaturePage } from '@/components/Landing/FeaturePage'
import { CONFIG } from '@/utils/config'
import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Collab',
  description:
    'Realtime collaborative documents, peer-to-peer. No accounts, no servers storing your text, no install.',
  openGraph: {
    siteName: 'Rapidly',
    type: 'website',
    images: [{ url: CONFIG.OG_IMAGE_URL, width: 1200, height: 630 }],
  },
}

const features = [
  {
    icon: 'Users',
    title: 'Realtime CRDT',
    description:
      'Every participant edits the same document and converges to the same state, no matter who typed what first.',
  },
  {
    icon: 'Lock',
    title: 'Local-first',
    description:
      "Nothing lives on our servers. The document stays in the peers' tabs and disappears when the last one closes.",
  },
  {
    icon: 'Link',
    title: 'One-click invite',
    description:
      'Start a doc, copy a link, paste it. The recipient joins and starts editing — no account, no install.',
  },
  {
    icon: 'Wifi',
    title: 'Works behind NATs',
    description:
      'Automatic Rapidly-hosted TURN fallback when a direct path is not possible, so your doc still syncs on coffee-shop Wi-Fi.',
  },
]

export default function CollabFeaturePage() {
  return (
    <FeaturePage
      description="Realtime collaborative documents without an account, server, or install. Open a doc, send a link, start typing together."
      features={features}
      ctaLabel="Start a doc"
      ctaHref="/collab"
      docsHref={CONFIG.DOCS_BASE_URL}
    />
  )
}
