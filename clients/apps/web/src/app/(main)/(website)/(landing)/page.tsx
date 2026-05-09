import { CONFIG } from '@/utils/config'
import { Metadata } from 'next'
import dynamicImport from 'next/dynamic'

const SecretViewer = dynamicImport(() =>
  import('@/components/Landing/SecretViewer').then((m) => m.SecretViewer),
)
const FileSharingLandingPage = dynamicImport(() =>
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

/** Landing page for secure P2P file sharing with secret viewer integration.
 *
 *  No SSR prefetch of the share counter. Earlier revisions awaited the
 *  ``/api/file-sharing/stats`` endpoint server-side and rendered the
 *  whole page dynamically (``force-dynamic``) so the count would be
 *  fresh — but the proxy round-trip plus the uncached render added
 *  ~700-1000 ms to every page load (visible as "logo click takes
 *  forever"). The counter component fetches client-side on mount, so
 *  the page can be served from cache instantly while the digit
 *  appears a moment later. The optimistic ``+1`` on share-created
 *  events still gives users immediate feedback for their own action. */
export default function Page() {
  return (
    <>
      <SecretViewer />
      <FileSharingLandingPage />
    </>
  )
}
