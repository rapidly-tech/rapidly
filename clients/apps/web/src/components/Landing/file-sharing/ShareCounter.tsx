'use client'

import { CONFIG } from '@/utils/config'
import { useCallback, useEffect, useState } from 'react'

// Hit the backend directly (api.rapidly.tech) instead of routing the
// stats request through the same-origin Next.js rewrite. Measured on
// prod: rewrite path ~990 ms, direct ~230 ms. The rewrite runs every
// request through the auth middleware (proxy.ts → /api/users/me),
// which the public stats endpoint doesn't need. CORS on api.rapidly.tech
// allows ``https://rapidly.tech`` with credentials, so this is safe.
const STATS_URL = `${CONFIG.BASE_URL}/api/file-sharing/stats`

// Inlined ``solar:share-linear`` SVG so the icon paints on first
// render rather than chasing a runtime fetch from
// ``api.iconify.design`` (visible delay on phones with cold caches).
function ShareIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="24"
      height="24"
      className={className}
      aria-hidden="true"
    >
      <g fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M9 12a2.5 2.5 0 1 1-5 0a2.5 2.5 0 0 1 5 0Z" />
        <path strokeLinecap="round" d="M14 6.5L9 10m5 7.5L9 14" />
        <path d="M19 18.5a2.5 2.5 0 1 1-5 0a2.5 2.5 0 0 1 5 0Zm0-13a2.5 2.5 0 1 1-5 0a2.5 2.5 0 0 1 5 0Z" />
      </g>
    </svg>
  )
}

const POLL_INTERVAL = 30_000 // 30s

/** Dispatch this event from anywhere on the page to trigger an immediate counter refresh. */
export const SHARE_CREATED_EVENT = 'rapidly:share-created'

/**
 * When `workspaceId` is provided, shows workspace-scoped session count
 * (requires the caller to be a member of that workspace). Otherwise
 * falls back to the public global stats endpoint.
 */
export const ShareCounter = ({ workspaceId }: { workspaceId?: string }) => {
  const [count, setCount] = useState<number | null>(null)

  const fetchCount = useCallback(async () => {
    try {
      const url = workspaceId
        ? `${STATS_URL}?workspace_id=${workspaceId}`
        : STATS_URL
      // ``credentials: 'include'`` so the backend's workspace-membership
      // check (#613) sees the auth cookie when ``workspaceId`` is set.
      const res = await fetch(url, {
        cache: 'no-store',
        credentials: 'include',
      })
      if (res.ok) {
        const data = await res.json()
        setCount(data.total_shares)
      }
    } catch {
      // cosmetic — silently ignore
    }
  }, [workspaceId])

  useEffect(() => {
    fetchCount()
    const id = setInterval(fetchCount, POLL_INTERVAL)

    // Optimistic +1 on share-created so the digit ticks the instant
    // the share completes, before the /stats round-trip lands.
    // ``fetchCount`` reconciles immediately after; if the optimistic
    // value matches the real one (the common case), no second
    // visual change.
    const onShareCreated = () => {
      setCount((c) => (typeof c === 'number' ? c + 1 : c))
      fetchCount()
    }
    window.addEventListener(SHARE_CREATED_EVENT, onShareCreated)

    return () => {
      clearInterval(id)
      window.removeEventListener(SHARE_CREATED_EVENT, onShareCreated)
    }
  }, [fetchCount])

  // Reserve the slot's vertical space via ``min-h`` so the landing
  // layout doesn't reflow when the number arrives. ``count === 0``
  // keeps the slot reserved but empty — nothing to brag about yet,
  // and reflowing later if the first share lands during the visit
  // would be jarring.
  const ready = count !== null && count > 0
  return (
    <div
      className="flex min-h-[3.25rem] flex-col items-center gap-1"
      aria-hidden={!ready}
    >
      {ready ? (
        <>
          {/* Render the value directly — no spring, no easing.
              Any tween puts a perceptible beat between ``setCount``
              and the digit changing; for single-digit deltas on a
              small number, a clean snap reads as more responsive. */}
          <span className="text-lg font-semibold tracking-tight text-slate-500 tabular-nums dark:text-slate-400">
            {count.toLocaleString('en-US')}
          </span>
          <div className="flex items-center gap-x-1.5">
            <ShareIcon className="h-3 w-3 text-slate-400 dark:text-slate-500" />
            <span className="rp-text-muted text-xs font-medium">
              shares so far
            </span>
          </div>
        </>
      ) : null}
    </div>
  )
}
