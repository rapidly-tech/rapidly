'use client'

/**
 * Mount-once component that wires the Phase 25e offline-shell SW via
 * the Phase 25d ``registerServiceWorker`` helper.
 *
 * Place it anywhere that renders on the routes you want offline-
 * capable. The demo page mounts it at the root; a future chamber
 * layout would mount it from ``app/collab/layout.tsx`` so every
 * ``/collab/...`` route picks up the shell cache.
 *
 * Surfaces an ""Update available"" banner when a new SW has finished
 * installing but the page is still controlled by the old one. Click
 * the banner → ``window.location.reload()`` so the new version takes
 * over. No custom state machine — ``registerServiceWorker`` already
 * debounces update events for us.
 */

import { useEffect, useState } from 'react'

import { registerServiceWorker } from '@/utils/collab/service-worker-registration'

interface Props {
  /** Override for staging / per-chamber deployments. Defaults to the
   *  ``/sw-collab.js`` path shipped in Phase 25e. */
  scriptPath?: string
  scope?: string
}

export function ServiceWorkerRegistrar({ scriptPath, scope }: Props) {
  const [updateAvailable, setUpdateAvailable] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    const handle = registerServiceWorker({
      scriptPath,
      scope,
      onUpdateAvailable: () => setUpdateAvailable(true),
      onError: (err) => setError(err),
    })
    return () => {
      // Best-effort — we don't unregister on unmount because other
      // mounted instances of this component (across pages) depend on
      // the registration. The handle.unregister() path is reserved
      // for explicit debug tooling.
      void handle
    }
  }, [scriptPath, scope])

  if (!updateAvailable && !error) return null

  if (error) {
    return (
      <div
        role="status"
        className="fixed inset-x-0 top-0 z-50 flex items-center justify-center gap-3 bg-amber-500/90 px-4 py-2 text-xs text-amber-950 shadow-md"
      >
        <span>Offline shell unavailable — live network only.</span>
      </div>
    )
  }

  return (
    <div
      role="status"
      className="fixed inset-x-0 top-0 z-50 flex items-center justify-center gap-3 bg-emerald-600 px-4 py-2 text-xs font-medium text-white shadow-md"
    >
      <span>A new version is available.</span>
      <button
        type="button"
        onClick={() => window.location.reload()}
        className="rounded-md bg-white/15 px-2 py-0.5 text-xs font-semibold text-white hover:bg-white/25"
      >
        Reload
      </button>
    </div>
  )
}
