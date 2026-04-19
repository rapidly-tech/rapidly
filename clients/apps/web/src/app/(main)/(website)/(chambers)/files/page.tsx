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

// Public files landing. The Revolver registry's "Files" chamber used
// to point at /dashboard (auth-gated) which bounced visitors to
// /login. This page renders the same FileSharingLandingPage the
// historical "/" uses, so clicking "Files" in the Revolver lands on
// the public share flow regardless of whether the Revolver landing
// flag is on or off.
export default function FilesLandingPage() {
  return <FileSharingLandingPage />
}
