import { CONFIG } from '@/utils/config'
import { Metadata } from 'next'
import dynamic from 'next/dynamic'

const SecretViewer = dynamic(() =>
  import('@/components/Landing/SecretViewer').then((m) => m.SecretViewer),
)
const FileSharingLandingPage = dynamic(() =>
  import('@/components/Landing/file-sharing/FileSharingLandingPage').then(
    (m) => m.FileSharingLandingPage,
  ),
)

export const metadata: Metadata = {
  // No ``title`` here — falls back to the root layout's default
  // (``Rapidly``) instead of formatting through the
  // ``%s | Rapidly`` template, which would produce
  // ``Home | Rapidly``. The home tab should read just "Rapidly".
  description:
    'Peer-to-peer file transfers in your browser. No uploads to servers, no size limits, fully encrypted with AES-256-GCM.',
  keywords:
    'file sharing, peer-to-peer, p2p, file transfer, secure, encrypted, webrtc, browser',
  openGraph: {
    siteName: 'File Sharing',
    type: 'website',
    images: [
      {
        url: CONFIG.OG_IMAGE_URL,
        width: 1200,
        height: 630,
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    images: [
      {
        url: CONFIG.OG_IMAGE_URL,
        width: 1200,
        height: 630,
        alt: 'Secure P2P File Sharing',
      },
    ],
  },
}

/** Landing page for secure P2P file sharing with secret viewer integration. */
export default function Page() {
  return (
    <>
      <SecretViewer />
      <FileSharingLandingPage />
    </>
  )
}
