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

/** Server-side prefetch of the public stats counter. Hits the
 *  backend directly (the ``/api/file-sharing`` proxy is a client-
 *  only Next.js rewrite — server fetches need an absolute URL),
 *  caches the result for 60 s via the route-level ``revalidate``
 *  contract so the count appears in the initial HTML and the
 *  client component doesn't have to wait for its first fetch.
 *
 *  Capped with a 2 s ``AbortController`` so a hanging backend
 *  can't slow the page render — the whole point of the SSR
 *  optimisation is making the page faster, so we'd rather fall
 *  through to the client-side poll than block.
 *
 *  Failures (network, non-OK status, malformed payload, timeout)
 *  fall through to ``undefined``. The client poll then runs as
 *  before, so a backend hiccup degrades to "counter shows up a
 *  moment later" rather than blowing up the page render. */
const STATS_FETCH_TIMEOUT_MS = 2_000

async function fetchInitialShareCount(): Promise<number | undefined> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), STATS_FETCH_TIMEOUT_MS)
  try {
    // Backend mounts file-sharing under ``/api/file-sharing`` (the
    // top-level router has ``prefix="/api"``, the file-sharing
    // sub-router adds ``/file-sharing``). The earlier ``/v1/...`` URL
    // here was wrong → 404 → SSR silently returned ``undefined``,
    // making the prefetch a no-op.
    const res = await fetch(`${CONFIG.BASE_URL}/api/file-sharing/stats`, {
      next: { revalidate: 60 },
      signal: controller.signal,
    })
    if (!res.ok) return undefined
    const data = (await res.json()) as { total_shares?: unknown }
    return typeof data.total_shares === 'number' ? data.total_shares : undefined
  } catch {
    return undefined
  } finally {
    clearTimeout(timer)
  }
}

/** Landing page for secure P2P file sharing with secret viewer integration. */
export default async function Page() {
  const initialShareCount = await fetchInitialShareCount()
  return (
    <>
      <SecretViewer />
      <FileSharingLandingPage initialShareCount={initialShareCount} />
    </>
  )
}
