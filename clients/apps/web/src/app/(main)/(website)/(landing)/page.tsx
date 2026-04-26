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
const RevolverLanding = dynamic(() =>
  import('@/components/Revolver/RevolverLanding').then(
    (m) => m.RevolverLanding,
  ),
)

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

/** Landing page for secure P2P file sharing with secret viewer integration.
 *
 * When ``NEXT_PUBLIC_REVOLVER_LANDING=true`` at build time, the 6-chamber
 * Revolver replaces the file-sharing hero so we can roll the new surface
 * out on a staging domain before flipping production traffic.
 */
export default function Page() {
  if (CONFIG.REVOLVER_LANDING_ENABLED) {
    return (
      <>
        <SecretViewer />
        <RevolverLanding />
      </>
    )
  }
  return (
    <>
      <SecretViewer />
      <FileSharingLandingPage />
    </>
  )
}
