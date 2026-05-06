import type { Metadata } from 'next'
import dynamic from 'next/dynamic'

// Lazy-load — the landing component imports Framer Motion + QR + a
// bunch of form primitives. Keeping it dynamic matches how the root
// landing route loads it.
const FileSharingLandingPage = dynamic(() =>
  import('@/components/Landing/file-sharing/FileSharingLandingPage').then(
    (m) => m.FileSharingLandingPage,
  ),
)

export const metadata: Metadata = {
  title: 'Files — Rapidly',
  description:
    'Peer-to-peer file transfers in your browser. No uploads to servers, no size limits, fully encrypted.',
}

// Public files landing. Renders the same FileSharingLandingPage the
// root ``/`` uses, so the chamber-strip nav has an unauth'd target
// to send visitors to.
export default function FilesLandingPage() {
  return <FileSharingLandingPage />
}
