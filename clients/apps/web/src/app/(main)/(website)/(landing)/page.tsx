import { SecretViewer } from '@/components/Landing/SecretViewer'
import { FileSharingLandingPage } from '@/components/Landing/file-sharing/FileSharingLandingPage'
import { CONFIG } from '@/utils/config'
import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Home',
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
