import type { Metadata } from 'next'

import { CollabPerfHarness } from '@/components/Collab/perf/CollabPerfHarness'

/**
 * Internal perf harness for the Collab v2 whiteboard rewrite.
 * Referenced by COLLAB_WHITEBOARD_PLAN.md §3.2 as the go/no-go signal
 * for "native canvas 2D is enough" vs "we need OffscreenCanvas + Worker."
 *
 * Not linked from anywhere in the product. Noindexed, robots-off.
 * Lives outside any (main) layout group so it renders without the
 * website nav + footer — we want a clean page to measure pure render
 * cost, not chrome.
 */

export const metadata: Metadata = {
  title: 'Collab perf harness — Rapidly (internal)',
  robots: { index: false, follow: false },
}

export default function CollabPerfPage() {
  return <CollabPerfHarness />
}
