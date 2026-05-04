import type { Metadata } from 'next'

import { CollabWhiteboard } from '@/components/Collab/CollabWhiteboard'

/** Internal demo page for the Collab v2 whiteboard. Mounts the real
 *  production component with no external props — its internal
 *  ``ElementStore`` + in-memory presence stub stand in for the chamber
 *  wiring. Used for visual regression + manual tool exercise. */

export const metadata: Metadata = {
  title: 'Collab whiteboard demo — Rapidly (internal)',
  robots: { index: false, follow: false },
}

export default function CollabWhiteboardDemoPage() {
  // CollabWhiteboard sizes to its parent (``h-full w-full``); on this
  // bare demo page we give it the viewport explicitly via fixed
  // positioning so the canvas has somewhere to render.
  return (
    <div className="fixed inset-0">
      <CollabWhiteboard />
    </div>
  )
}
