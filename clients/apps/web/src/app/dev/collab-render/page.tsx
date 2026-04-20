import type { Metadata } from 'next'

import { CollabRenderDemo } from '@/components/Collab/dev/CollabRenderDemo'

/** Internal demo of the Collab v2 renderer (Phase 1b).
 *
 *  Builds a small scene of rects + ellipses in an ``ElementStore``,
 *  mounts a ``Renderer``, and wires pan / zoom / hit-test. No Yjs
 *  networking — the store is local. Purpose is to prove the renderer
 *  orchestration works end-to-end before any tool / multi-peer code
 *  lands on top. */

export const metadata: Metadata = {
  title: 'Collab renderer demo — Rapidly (internal)',
  robots: { index: false, follow: false },
}

export default function CollabRenderDemoPage() {
  return <CollabRenderDemo />
}
