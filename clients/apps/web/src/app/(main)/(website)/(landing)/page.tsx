import { CONFIG } from '@/utils/config'
import { Metadata } from 'next'
import dynamicImport from 'next/dynamic'

// Force dynamic rendering on every request. Without this Next.js
// fully-cached the rendered HTML (``cache-control: s-maxage=...``,
// ``x-nextjs-cache: HIT``) regardless of ``cache: 'no-store'`` on
// the inner stats fetch — visitors were getting an HTML page with
// a stats value baked in at the time of the first render and only
// the client-side poll would correct it (visible as "the counter
// shows a lower number first and then goes back up").
export const dynamic = 'force-dynamic'

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

/** Server-side prefetch of the public stats counter. ``cache:
 *  'no-store'`` so each request fetches the live value — the
 *  previous ``revalidate: 60`` made the SSR HTML up to a minute
 *  stale, which the user perceived as "the counter shows a lower
 *  number first and then goes back up". Backend already has its
 *  own 15 s cache (``_STATS_CACHE_KEY``) so the load is bounded
 *  to one Redis read per worker per ~15 s.
 *
 *  Capped with a 2 s ``AbortController`` so a hanging backend
 *  can't slow the page render — failures fall through to
 *  ``undefined`` and the client component fetches on mount. */
const STATS_FETCH_TIMEOUT_MS = 2_000

async function fetchInitialShareCount(): Promise<number | undefined> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), STATS_FETCH_TIMEOUT_MS)
  try {
    const res = await fetch(`${CONFIG.BASE_URL}/api/file-sharing/stats`, {
      cache: 'no-store',
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
